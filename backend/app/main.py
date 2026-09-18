from pathlib import Path
import json

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from app.supabase_client import supabase
from app.simulator import simulate_well_tick
from app.optimizer import (
    optimize_well_fast,
    batch_predict,
    calculate_mechanical_state,
    calculate_energy,
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="WellWise API",
    description="AI-Powered Baghewala Digital Twin API",
    version="1.0.0",
)


# ============================================================
# CORS
# Temporary development configuration
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# LOAD TRAINED MODELS
# ============================================================

model1 = joblib.load(
    MODEL_DIR / "model1_final.pkl"
)

model2 = joblib.load(
    MODEL_DIR / "model2_final.pkl"
)

model3 = joblib.load(
    MODEL_DIR / "model3_final.pkl"
)


# ============================================================
# LOAD PREPROCESSORS
# ============================================================

preprocessor1 = joblib.load(
    MODEL_DIR / "model1_preprocessor.pkl"
)

preprocessor2 = joblib.load(
    MODEL_DIR / "model2_preprocessor.pkl"
)

preprocessor3 = joblib.load(
    MODEL_DIR / "model3_preprocessor.pkl"
)


# ============================================================
# LOAD FEATURE LISTS
# ============================================================

features1 = joblib.load(
    MODEL_DIR / "model1_features.pkl"
)

features2 = joblib.load(
    MODEL_DIR / "model2_features.pkl"
)

features3 = joblib.load(
    MODEL_DIR / "model3_features.pkl"
)


# ============================================================
# LOAD MODEL 3 THRESHOLD
# ============================================================

with open(
    MODEL_DIR / "model3_metadata.json",
    "r"
) as file:
    model3_metadata = json.load(file)


rod_threshold = float(
    model3_metadata["threshold"]
)


# ============================================================
# PREPARE MODEL MATRIX
# ============================================================

def prepare_model_matrix(
    data: pd.DataFrame,
    encoder,
    feature_list,
) -> pd.DataFrame:

    df = data.copy()

    # --------------------------------------------------------
    # Timestamp-derived features
    # These existed in the original training pipeline.
    # --------------------------------------------------------

    if "timestamp" in df.columns:

        df["timestamp"] = pd.to_datetime(
            df["timestamp"]
        )

        df["hour"] = (
            df["timestamp"].dt.hour
        )

        df["day_of_week"] = (
            df["timestamp"].dt.dayofweek
        )

        df["month"] = (
            df["timestamp"].dt.month
        )

    # --------------------------------------------------------
    # Encode cycle phase
    # --------------------------------------------------------

    if "cycle_phase" in df.columns:

        encoded = encoder.transform(
            df[["cycle_phase"]]
        )

        encoded_columns = [
            f"cycle_phase_{category}"
            for category in encoder.categories_[0]
        ]

        encoded_df = pd.DataFrame(
            encoded,
            columns=encoded_columns,
            index=df.index,
        )

        df = df.drop(
            columns=["cycle_phase"]
        )

        df = pd.concat(
            [
                df,
                encoded_df,
            ],
            axis=1,
        )

    # --------------------------------------------------------
    # Add missing expected features
    # --------------------------------------------------------

    for column in feature_list:

        if column not in df.columns:

            df[column] = 0.0

    # --------------------------------------------------------
    # Exact training feature order
    # --------------------------------------------------------

    df = df[
        feature_list
    ]

    return df.astype(float)


# ============================================================
# HEALTH
# ============================================================
class WhatIfRequest(BaseModel):
    steam_rate: float
    steam_temperature: float
    injection_pressure: float
    injection_duration: float
    soak_time: float
    stroke_length: float
    spm: float
    vfd_frequency: float | None = None
@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "service": "WellWise API",
        "models_loaded": True,
        "optimizer_loaded": True,
        "telemetry_source": "SIMULATED",
    }


# ============================================================
# WELLS
# ============================================================

@app.get("/api/wells")
def get_wells():

    response = (
        supabase
        .table("wells")
        .select("*")
        .order("well_id")
        .execute()
    )

    return response.data


# ============================================================
# LATEST TELEMETRY
# ============================================================
@app.get("/api/telemetry-history/{well_id}")
def get_telemetry_history(
    well_id: str,
    limit: int = 144
):
    # Keep the limit within a safe range.
    limit = max(1, min(limit, 1000))

    response = (
        supabase
        .table("telemetry")
        .select(
            "id,well_id,timestamp,"
            "reservoir_temperature,"
            "reservoir_pressure,"
            "current_oil_rate,"
            "current_water_rate,"
            "current_energy,"
            "fluid_level,"
            "spm,"
            "stroke_length,"
            "vfd_frequency,"
            "rod_load,"
            "pump_load,"
            "pump_fillage"
        )
        .eq("well_id", well_id)
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )

    rows = response.data or []

    return [
        {
            "id": row["id"],
            "well_id": row["well_id"],
            "timestamp": row["timestamp"],
            "reservoir_temperature": row["reservoir_temperature"],
            "reservoir_pressure": row["reservoir_pressure"],
            "oil_rate": row["current_oil_rate"],
            "water_rate": row["current_water_rate"],
            "energy": row["current_energy"],
            "fluid_level": row["fluid_level"],
            "spm": row["spm"],
            "stroke_length": row["stroke_length"],
            "vfd_frequency": row["vfd_frequency"],
            "rod_load": row["rod_load"],
            "pump_load": row["pump_load"],
            "pump_fillage": row["pump_fillage"],
        }
        for row in rows
    ]
@app.get("/api/telemetry/{well_id}")
def get_latest_telemetry(
    well_id: str
):

    response = (
        supabase
        .table("telemetry")
        .select("*")
        .eq("well_id", well_id)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:

        raise HTTPException(
            status_code=404,
            detail=f"No telemetry found for {well_id}",
        )

    return response.data[0]


# ============================================================
# PREDICTION
# ============================================================

@app.get("/api/predict/{well_id}")
def predict_well(
    well_id: str
):
    """
    Run the 3 trained WellWise XGBoost models using the
    latest telemetry + static well parameters.

    The prediction is also saved into Supabase.
    """

    # --------------------------------------------------------
    # Latest telemetry
    # --------------------------------------------------------

    telemetry_response = (
        supabase
        .table("telemetry")
        .select("*")
        .eq("well_id", well_id)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )

    if not telemetry_response.data:

        raise HTTPException(
            status_code=404,
            detail=f"No telemetry found for {well_id}",
        )

    telemetry = telemetry_response.data[0]

    # --------------------------------------------------------
    # Static well parameters
    # --------------------------------------------------------

    well_response = (
        supabase
        .table("wells")
        .select("*")
        .eq("well_id", well_id)
        .limit(1)
        .execute()
    )

    if not well_response.data:

        raise HTTPException(
            status_code=404,
            detail=f"Well {well_id} not found",
        )

    well = well_response.data[0]

    # --------------------------------------------------------
    # Combine telemetry + static well values
    # --------------------------------------------------------

    current_raw = telemetry.copy()

    current_raw["api_gravity"] = well.get(
        "api_gravity",
        0.0
    )

    current_raw["asphaltene_content"] = well.get(
        "asphaltene_content",
        0.0
    )

    current_raw = pd.DataFrame(
        [current_raw]
    )

    # --------------------------------------------------------
    # Prepare 3 model inputs
    # --------------------------------------------------------

    X1 = prepare_model_matrix(
        current_raw,
        preprocessor1,
        features1,
    )

    X2 = prepare_model_matrix(
        current_raw,
        preprocessor2,
        features2,
    )

    X3 = prepare_model_matrix(
        current_raw,
        preprocessor3,
        features3,
    )

    # --------------------------------------------------------
    # Model 1
    # Future reservoir temperature
    # --------------------------------------------------------

    predicted_temperature = float(
        model1.predict(X1)[0]
    )

    # --------------------------------------------------------
    # Model 2
    # Future oil rate
    # --------------------------------------------------------

    predicted_oil_rate = float(
        model2.predict(X2)[0]
    )

    # --------------------------------------------------------
    # Model 3
    # Rod floating probability
    # --------------------------------------------------------

    rod_probability = float(
        model3.predict_proba(X3)[0, 1]
    )

    rod_risk_pct = (
        rod_probability * 100.0
    )

    rod_status = (
        "FLOATING RISK"
        if rod_probability >= rod_threshold
        else "NORMAL"
    )

    # --------------------------------------------------------
    # Save prediction to Supabase
    # --------------------------------------------------------

    prediction_row = {

        "well_id":
            well_id,

        "telemetry_id":
            telemetry["id"],

        "predicted_at":
            telemetry["timestamp"],

        "prediction_horizon_hours":
            24,

        "future_reservoir_temperature":
            predicted_temperature,

        "future_oil_rate":
            predicted_oil_rate,

        "rod_floating_probability":
            rod_probability,

        "rod_floating_risk_pct":
            rod_risk_pct,

        "rod_status":
            rod_status,

        "model_version":
            "WellWise-XGBoost-v1",
    }

    prediction_response = (
        supabase
        .table("predictions")
        .insert(prediction_row)
        .execute()
    )

    saved_prediction = (
        prediction_response.data[0]
        if prediction_response.data
        else None
    )

    # --------------------------------------------------------
    # API response
    # --------------------------------------------------------

    return {

        "well_id":
            well_id,

        "telemetry_id":
            telemetry["id"],

        "timestamp":
            telemetry["timestamp"],

        "source":
            telemetry.get(
                "source",
                "SIMULATED"
            ),

        "current_state": {

            "reservoir_temperature":
                telemetry["reservoir_temperature"],

            "reservoir_pressure":
                telemetry["reservoir_pressure"],

            "oil_viscosity":
                telemetry["oil_viscosity"],

            "current_oil_rate":
                telemetry["current_oil_rate"],

            "current_water_rate":
                telemetry["current_water_rate"],

            "spm":
                telemetry["spm"],

            "stroke_length":
                telemetry["stroke_length"],

            "vfd_frequency":
                telemetry["vfd_frequency"],

            "current_energy":
                telemetry["current_energy"],

            "rod_load":
                telemetry["rod_load"],

            "pump_load":
                telemetry["pump_load"],

            "pump_fillage":
                telemetry["pump_fillage"],

            "fluid_level":
                telemetry["fluid_level"],
        },

        "prediction_24h": {

            "future_reservoir_temperature":
                predicted_temperature,

            "future_oil_rate":
                predicted_oil_rate,

            "rod_floating_probability":
                rod_probability,

            "rod_floating_risk_pct":
                rod_risk_pct,

            "rod_status":
                rod_status,
        },

        "prediction_id":
            saved_prediction["id"]
            if saved_prediction
            else None,
    }


# ============================================================
# SIMULATOR
# ============================================================

@app.get("/api/simulate/{well_id}")
def simulate_well(
    well_id: str
):
    """
    Generate one controlled simulated telemetry tick
    for a well and save it to Supabase.
    """

    try:

        result = simulate_well_tick(
            well_id
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# OPTIMIZER
# ============================================================

@app.get("/api/optimize/{well_id}")
def optimize_well(
    well_id: str
):
    """
    Run CSS + SRP Optimizer V2.1 and save the resulting
    recommendation into Supabase.
    """

    # --------------------------------------------------------
    # Latest telemetry
    # --------------------------------------------------------

    telemetry_response = (
        supabase
        .table("telemetry")
        .select("*")
        .eq("well_id", well_id)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )

    if not telemetry_response.data:
        raise HTTPException(
            status_code=404,
            detail=f"No telemetry found for {well_id}",
        )

    telemetry = telemetry_response.data[0]

    # --------------------------------------------------------
    # Static well parameters
    # --------------------------------------------------------

    well_response = (
        supabase
        .table("wells")
        .select("*")
        .eq("well_id", well_id)
        .limit(1)
        .execute()
    )

    if not well_response.data:
        raise HTTPException(
            status_code=404,
            detail=f"Well {well_id} not found",
        )

    well = well_response.data[0]

    # --------------------------------------------------------
    # Combine telemetry + static parameters
    # --------------------------------------------------------

    current_raw = telemetry.copy()

    current_raw["api_gravity"] = well.get(
        "api_gravity",
        0.0
    )

    current_raw["asphaltene_content"] = well.get(
        "asphaltene_content",
        0.0
    )

    current_raw = pd.Series(
        current_raw
    )

    # --------------------------------------------------------
    # Run optimizer
    # --------------------------------------------------------

    result = optimize_well_fast(
        current_raw,
        n_candidates=1000,
    )

    # --------------------------------------------------------
    # No feasible candidate
    # --------------------------------------------------------

    if result["recommended"] is None:

        return {
            "well_id": well_id,
            "status": result["status"],
            "timestamp": telemetry["timestamp"],
            "baseline": result["baseline"],
            "feasible_candidates": 0,
            "recommendation": None,
        }

    recommended = result["recommended"]

    # --------------------------------------------------------
    # Find prediction belonging to this telemetry
    # --------------------------------------------------------

    prediction_response = (
        supabase
        .table("predictions")
        .select("id")
        .eq("well_id", well_id)
        .eq("telemetry_id", telemetry["id"])
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    # --------------------------------------------------------
    # Use existing prediction if available
    # Otherwise save optimizer baseline as prediction
    # --------------------------------------------------------

    if prediction_response.data:

        prediction_id = (
            prediction_response.data[0]["id"]
        )

    else:

        baseline = result["baseline"]

        baseline_probability = (
            float(baseline["risk"]) / 100.0
        )

        baseline_status = (
            "FLOATING RISK"
            if baseline_probability >= rod_threshold
            else "NORMAL"
        )

        new_prediction = {

            "well_id":
                well_id,

            "telemetry_id":
                telemetry["id"],

            "predicted_at":
                telemetry["timestamp"],

            "prediction_horizon_hours":
                24,

            "future_reservoir_temperature":
                float(
                    baseline["temperature"]
                ),

            "future_oil_rate":
                float(
                    baseline["oil"]
                ),

            "rod_floating_probability":
                baseline_probability,

            "rod_floating_risk_pct":
                float(
                    baseline["risk"]
                ),

            "rod_status":
                baseline_status,

            "model_version":
                "WellWise-XGBoost-v1",
        }

        created_prediction = (
            supabase
            .table("predictions")
            .insert(new_prediction)
            .execute()
        )

        if not created_prediction.data:

            raise HTTPException(
                status_code=500,
                detail="Failed to save prediction",
            )

        prediction_id = (
            created_prediction.data[0]["id"]
        )

    # --------------------------------------------------------
    # Build recommendation record
    # --------------------------------------------------------

    recommendation_row = {

        "well_id":
            well_id,

        "prediction_id":
            prediction_id,

        "steam_rate":
            float(
                recommended["steam_rate"]
            ),

        "steam_temperature":
            float(
                recommended["steam_temperature"]
            ),

        "injection_pressure":
            float(
                recommended["injection_pressure"]
            ),

        "injection_duration":
            float(
                recommended["injection_duration"]
            ),

        "soak_time":
            float(
                recommended["soak_time"]
            ),

        "steam_volume":
            float(
                recommended["steam_volume"]
            ),

        "stroke_length":
            float(
                recommended["stroke_length"]
            ),

        "spm":
            float(
                recommended["spm"]
            ),

        "vfd_frequency":
            float(
                recommended["vfd_frequency"]
            ),

        "predicted_reservoir_temperature":
            float(
                recommended["pred_temperature"]
            ),

        "predicted_oil_rate":
            float(
                recommended["pred_oil"]
            ),

        "predicted_rod_risk_pct":
            float(
                recommended["rod_risk"]
            ),

        "predicted_energy":
            float(
                recommended["energy"]
            ),

        "sor_proxy":
            float(
                recommended["sor_proxy"]
            ),

        "optimization_score":
            float(
                recommended["optimization_score"]
            ),

        "oil_change_pct":
            float(
                recommended["oil_change_pct"]
            ),

        "risk_change_pct":
            float(
                recommended["risk_change_pct"]
            ),

        "energy_change_pct":
            float(
                recommended["energy_change_pct"]
            ),

        "optimizer_status":
            result["status"],

        "candidate_count":
            1000,

        "feasible_candidate_count":
            int(
                len(
                    result["feasible"]
                )
            ),

        "optimizer_version":
            "WellWise-Optimizer-V2.1",
    }

    # --------------------------------------------------------
    # Save recommendation
    # --------------------------------------------------------

    recommendation_response = (
        supabase
        .table("recommendations")
        .insert(recommendation_row)
        .execute()
    )

    saved_recommendation = (
        recommendation_response.data[0]
        if recommendation_response.data
        else None
    )

    # --------------------------------------------------------
    # Return response
    # --------------------------------------------------------

    return {

        "well_id":
            well_id,

        "status":
            result["status"],

        "timestamp":
            telemetry["timestamp"],

        "prediction_id":
            prediction_id,

        "recommendation_id":
            saved_recommendation["id"]
            if saved_recommendation
            else None,

        "baseline":
            result["baseline"],

        "feasible_candidates":
            int(
                len(
                    result["feasible"]
                )
            ),

        "recommendation": {

            "steam_rate":
                float(
                    recommended["steam_rate"]
                ),

            "steam_temperature":
                float(
                    recommended["steam_temperature"]
                ),

            "injection_pressure":
                float(
                    recommended["injection_pressure"]
                ),

            "injection_duration":
                float(
                    recommended["injection_duration"]
                ),

            "soak_time":
                float(
                    recommended["soak_time"]
                ),

            "steam_volume":
                float(
                    recommended["steam_volume"]
                ),

            "stroke_length":
                float(
                    recommended["stroke_length"]
                ),

            "spm":
                float(
                    recommended["spm"]
                ),

            "vfd_frequency":
                float(
                    recommended["vfd_frequency"]
                ),

            "predicted_temperature":
                float(
                    recommended["pred_temperature"]
                ),

            "predicted_oil_rate":
                float(
                    recommended["pred_oil"]
                ),

            "predicted_rod_risk":
                float(
                    recommended["rod_risk"]
                ),

            "predicted_energy":
                float(
                    recommended["energy"]
                ),

            "sor_proxy":
                float(
                    recommended["sor_proxy"]
                ),

            "oil_change_pct":
                float(
                    recommended["oil_change_pct"]
                ),

            "risk_change_pct":
                float(
                    recommended["risk_change_pct"]
                ),

            "energy_change_pct":
                float(
                    recommended["energy_change_pct"]
                ),

            "optimization_score":
                float(
                    recommended["optimization_score"]
                ),
        },
    }
# ============================================================
# WHAT-IF SIMULATION
# ============================================================

@app.post("/api/what-if/{well_id}")
def what_if_simulation(
    well_id: str,
    request: WhatIfRequest,
):
    """
    Simulate one engineer-defined CSS + SRP scenario.

    This endpoint does NOT modify telemetry, predictions,
    recommendations, or operating settings.
    """

    # --------------------------------------------------------
    # Get latest telemetry
    # --------------------------------------------------------

    telemetry_response = (
        supabase
        .table("telemetry")
        .select("*")
        .eq("well_id", well_id)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )

    if not telemetry_response.data:
        raise HTTPException(
            status_code=404,
            detail=f"No telemetry found for {well_id}",
        )

    telemetry = telemetry_response.data[0]

    # --------------------------------------------------------
    # Get static well parameters
    # --------------------------------------------------------

    well_response = (
        supabase
        .table("wells")
        .select("*")
        .eq("well_id", well_id)
        .limit(1)
        .execute()
    )

    if not well_response.data:
        raise HTTPException(
            status_code=404,
            detail=f"Well {well_id} not found",
        )

    well = well_response.data[0]

    # --------------------------------------------------------
    # Validate well operating limits
    # --------------------------------------------------------

    if (
        well.get("max_steam_rate") is not None
        and request.steam_rate
        > float(well["max_steam_rate"])
    ):
        raise HTTPException(
            status_code=400,
            detail="Steam rate exceeds the well maximum.",
        )

    if (
        well.get("min_injection_pressure") is not None
        and request.injection_pressure
        < float(well["min_injection_pressure"])
    ):
        raise HTTPException(
            status_code=400,
            detail="Injection pressure is below the well minimum.",
        )

    if (
        well.get("max_injection_pressure") is not None
        and request.injection_pressure
        > float(well["max_injection_pressure"])
    ):
        raise HTTPException(
            status_code=400,
            detail="Injection pressure exceeds the well maximum.",
        )

    if (
        well.get("min_spm") is not None
        and request.spm
        < float(well["min_spm"])
    ):
        raise HTTPException(
            status_code=400,
            detail="SPM is below the well minimum.",
        )

    if (
        well.get("max_spm") is not None
        and request.spm
        > float(well["max_spm"])
    ):
        raise HTTPException(
            status_code=400,
            detail="SPM exceeds the well maximum.",
        )

    if (
        well.get("min_stroke_length") is not None
        and request.stroke_length
        < float(well["min_stroke_length"])
    ):
        raise HTTPException(
            status_code=400,
            detail="Stroke length is below the well minimum.",
        )

    if (
        well.get("max_stroke_length") is not None
        and request.stroke_length
        > float(well["max_stroke_length"])
    ):
        raise HTTPException(
            status_code=400,
            detail="Stroke length exceeds the well maximum.",
        )

    # --------------------------------------------------------
    # VFD
    # --------------------------------------------------------

    if request.vfd_frequency is None:

        vfd_frequency = float(
            max(
                20.0,
                min(
                    60.0,
                    20.0
                    + (request.spm / 3.0) * 40.0,
                ),
            )
        )

    else:

        vfd_frequency = float(
            request.vfd_frequency
        )

    if (
        well.get("min_vfd_frequency") is not None
        and vfd_frequency
        < float(well["min_vfd_frequency"])
    ):
        raise HTTPException(
            status_code=400,
            detail="VFD frequency is below the well minimum.",
        )

    if (
        well.get("max_vfd_frequency") is not None
        and vfd_frequency
        > float(well["max_vfd_frequency"])
    ):
        raise HTTPException(
            status_code=400,
            detail="VFD frequency exceeds the well maximum.",
        )

    # --------------------------------------------------------
    # Build baseline input
    # --------------------------------------------------------

    baseline_raw = telemetry.copy()

    baseline_raw["api_gravity"] = well.get(
        "api_gravity",
        0.0,
    )

    baseline_raw["asphaltene_content"] = well.get(
        "asphaltene_content",
        0.0,
    )

    baseline_df = pd.DataFrame(
        [baseline_raw]
    )

    # --------------------------------------------------------
    # Baseline prediction
    # --------------------------------------------------------

    (
        baseline_temp,
        baseline_oil,
        baseline_risk,
    ) = batch_predict(
        baseline_df
    )

    baseline_temp = float(
        baseline_temp[0]
    )

    baseline_oil = float(
        baseline_oil[0]
    )

    baseline_risk_pct = float(
        baseline_risk[0] * 100.0
    )

    baseline_energy = float(
        telemetry["current_energy"]
    )

    # --------------------------------------------------------
    # Build What-If scenario
    # --------------------------------------------------------

    scenario = telemetry.copy()

    scenario["api_gravity"] = well.get(
        "api_gravity",
        0.0,
    )

    scenario["asphaltene_content"] = well.get(
        "asphaltene_content",
        0.0,
    )

    scenario["steam_rate"] = (
        request.steam_rate
    )

    scenario["steam_temperature"] = (
        request.steam_temperature
    )

    scenario["injection_pressure"] = (
        request.injection_pressure
    )

    scenario["injection_duration"] = (
        request.injection_duration
    )

    scenario["soak_time"] = (
        request.soak_time
    )

    scenario["stroke_length"] = (
        request.stroke_length
    )

    scenario["spm"] = (
        request.spm
    )

    scenario["vfd_frequency"] = (
        vfd_frequency
    )

    # --------------------------------------------------------
    # Steam volume
    # Same calculation used by Optimizer V2.1
    # --------------------------------------------------------

    scenario["steam_volume"] = (
        request.steam_rate
        * request.injection_duration
        * 24.0
    )

    # --------------------------------------------------------
    # Mechanical state
    # Same calculation used by Optimizer V2.1
    # --------------------------------------------------------

    (
        rod_load,
        pump_load,
        pump_fillage,
    ) = calculate_mechanical_state(
        float(
            scenario["oil_viscosity"]
        ),
        float(
            scenario["reservoir_pressure"]
        ),
        float(
            request.spm
        ),
    )

    scenario["rod_load"] = float(
        rod_load
    )

    scenario["pump_load"] = float(
        pump_load
    )

    scenario["pump_fillage"] = float(
        pump_fillage
    )

    # --------------------------------------------------------
    # Energy
    # --------------------------------------------------------

    scenario_energy = float(
        calculate_energy(
            vfd_frequency,
            float(pump_load),
        )
    )

    scenario["current_energy"] = (
        scenario_energy
    )

    # --------------------------------------------------------
    # Predict What-If scenario
    # --------------------------------------------------------

    scenario_df = pd.DataFrame(
        [scenario]
    )

    (
        predicted_temp,
        predicted_oil,
        predicted_risk,
    ) = batch_predict(
        scenario_df
    )

    predicted_temp = float(
        predicted_temp[0]
    )

    predicted_oil = float(
        predicted_oil[0]
    )

    predicted_risk_pct = float(
        predicted_risk[0] * 100.0
    )

    # --------------------------------------------------------
    # Calculate changes
    # --------------------------------------------------------

    oil_change_pct = (
        (
            predicted_oil
            - baseline_oil
        )
        / max(
            abs(baseline_oil),
            1e-9,
        )
    ) * 100.0

    risk_change_pct = (
        (
            predicted_risk_pct
            - baseline_risk_pct
        )
        / max(
            abs(baseline_risk_pct),
            1e-9,
        )
    ) * 100.0

    energy_change_pct = (
        (
            scenario_energy
            - baseline_energy
        )
        / max(
            abs(baseline_energy),
            1e-9,
        )
    ) * 100.0

    sor_proxy = (
        scenario["steam_volume"]
        / max(
            predicted_oil,
            1.0,
        )
    )

    rod_status = (
        "FLOATING RISK"
        if predicted_risk[0]
        >= rod_threshold
        else "NORMAL"
    )

    # --------------------------------------------------------
    # Return What-If result
    # --------------------------------------------------------

    return {

        "well_id":
            well_id,

        "timestamp":
            telemetry["timestamp"],

        "simulation_type":
            "WHAT_IF",

        "saved_to_database":
            False,

        "baseline": {

            "temperature":
                baseline_temp,

            "oil_rate":
                baseline_oil,

            "rod_risk_pct":
                baseline_risk_pct,

            "energy":
                baseline_energy,
        },

        "scenario": {

            "steam_rate":
                request.steam_rate,

            "steam_temperature":
                request.steam_temperature,

            "injection_pressure":
                request.injection_pressure,

            "injection_duration":
                request.injection_duration,

            "soak_time":
                request.soak_time,

            "steam_volume":
                float(
                    scenario["steam_volume"]
                ),

            "stroke_length":
                request.stroke_length,

            "spm":
                request.spm,

            "vfd_frequency":
                vfd_frequency,
        },

        "predicted_outcome": {

            "temperature":
                predicted_temp,

            "oil_rate":
                predicted_oil,

            "rod_risk_pct":
                predicted_risk_pct,

            "rod_status":
                rod_status,

            "energy":
                scenario_energy,

            "sor_proxy":
                sor_proxy,
        },

        "changes_vs_baseline": {

            "oil_change_pct":
                oil_change_pct,

            "risk_change_pct":
                risk_change_pct,

            "energy_change_pct":
                energy_change_pct,
        },
    }
# ============================================================
# DIGITAL TWIN OVERVIEW
# ============================================================

@app.get("/api/digital-twin/{well_id}")
def digital_twin(
    well_id: str
):
    """
    Return the complete Digital Twin view for one well.

    This endpoint combines:
    - latest telemetry
    - 24h ML predictions
    - CSS + SRP optimization

    It does not apply any operating change automatically.
    """

    # --------------------------------------------------------
    # Latest telemetry
    # --------------------------------------------------------

    telemetry_response = (
        supabase
        .table("telemetry")
        .select("*")
        .eq("well_id", well_id)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )

    if not telemetry_response.data:
        raise HTTPException(
            status_code=404,
            detail=f"No telemetry found for {well_id}",
        )

    telemetry = telemetry_response.data[0]

    # --------------------------------------------------------
    # Well configuration
    # --------------------------------------------------------

    well_response = (
        supabase
        .table("wells")
        .select("*")
        .eq("well_id", well_id)
        .limit(1)
        .execute()
    )

    if not well_response.data:
        raise HTTPException(
            status_code=404,
            detail=f"Well {well_id} not found",
        )

    well = well_response.data[0]

    # --------------------------------------------------------
    # Build ML input
    # --------------------------------------------------------

    current_raw = telemetry.copy()

    current_raw["api_gravity"] = well.get(
        "api_gravity",
        0.0
    )

    current_raw["asphaltene_content"] = well.get(
        "asphaltene_content",
        0.0
    )

    current_df = pd.DataFrame(
        [current_raw]
    )

    # --------------------------------------------------------
    # Run the 3 XGBoost models
    # --------------------------------------------------------

    X1 = prepare_model_matrix(
        current_df,
        preprocessor1,
        features1,
    )

    X2 = prepare_model_matrix(
        current_df,
        preprocessor2,
        features2,
    )

    X3 = prepare_model_matrix(
        current_df,
        preprocessor3,
        features3,
    )

    predicted_temperature = float(
        model1.predict(X1)[0]
    )

    predicted_oil_rate = float(
        model2.predict(X2)[0]
    )

    rod_probability = float(
        model3.predict_proba(X3)[0, 1]
    )

    rod_risk_pct = (
        rod_probability * 100.0
    )

    rod_status = (
        "FLOATING RISK"
        if rod_probability >= rod_threshold
        else "NORMAL"
    )

    # --------------------------------------------------------
    # Run optimizer
    # --------------------------------------------------------

    optimizer_input = pd.Series(
    current_raw
)

    optimizer_result = optimize_well_fast(
        optimizer_input,
        n_candidates=1000,
    )

    # --------------------------------------------------------
    # Recommendation
    # --------------------------------------------------------

    recommendation = None

    if optimizer_result["recommended"] is not None:

        r = optimizer_result[
            "recommended"
        ]

        recommendation = {

            "steam_rate":
                float(r["steam_rate"]),

            "steam_temperature":
                float(r["steam_temperature"]),

            "injection_pressure":
                float(r["injection_pressure"]),

            "injection_duration":
                float(r["injection_duration"]),

            "soak_time":
                float(r["soak_time"]),

            "steam_volume":
                float(r["steam_volume"]),

            "stroke_length":
                float(r["stroke_length"]),

            "spm":
                float(r["spm"]),

            "vfd_frequency":
                float(r["vfd_frequency"]),

            "predicted_temperature":
                float(r["pred_temperature"]),

            "predicted_oil_rate":
                float(r["pred_oil"]),

            "predicted_rod_risk":
                float(r["rod_risk"]),

            "predicted_energy":
                float(r["energy"]),

            "sor_proxy":
                float(r["sor_proxy"]),

            "oil_change_pct":
                float(r["oil_change_pct"]),

            "risk_change_pct":
                float(r["risk_change_pct"]),

            "energy_change_pct":
                float(r["energy_change_pct"]),

            "optimization_score":
                float(r["optimization_score"]),
        }

    # --------------------------------------------------------
    # Complete Digital Twin response
    # --------------------------------------------------------

    return {

        "well": {

            "well_id":
                well_id,

            "field":
                well.get("field_name"),

            "reservoir":
                well.get("reservoir_name"),

            "formation":
                well.get("formation_name"),

            "status":
                well.get("well_status"),

            "api_gravity":
                well.get("api_gravity"),

            "asphaltene_content":
                well.get(
                    "asphaltene_content"
                ),
        },

        "telemetry": {

            "timestamp":
                telemetry["timestamp"],

            "source":
                telemetry.get(
                    "source",
                    "SIMULATED"
                ),

            "reservoir_temperature":
                telemetry[
                    "reservoir_temperature"
                ],

            "reservoir_pressure":
                telemetry[
                    "reservoir_pressure"
                ],

            "oil_viscosity":
                telemetry[
                    "oil_viscosity"
                ],

            "oil_rate":
                telemetry[
                    "current_oil_rate"
                ],

            "water_rate":
                telemetry[
                    "current_water_rate"
                ],

            "energy":
                telemetry[
                    "current_energy"
                ],

            "fluid_level":
                telemetry[
                    "fluid_level"
                ],

            "spm":
                telemetry["spm"],

            "stroke_length":
                telemetry[
                    "stroke_length"
                ],

            "vfd_frequency":
                telemetry[
                    "vfd_frequency"
                ],

            "rod_load":
                telemetry[
                    "rod_load"
                ],

            "pump_load":
                telemetry[
                    "pump_load"
                ],

            "pump_fillage":
                telemetry[
                    "pump_fillage"
                ],
        },

        "prediction_24h": {

            "reservoir_temperature":
                predicted_temperature,

            "oil_rate":
                predicted_oil_rate,

            "rod_floating_probability":
                rod_probability,

            "rod_floating_risk_pct":
                rod_risk_pct,

            "rod_status":
                rod_status,
        },

        "optimization": {

            "status":
                optimizer_result["status"],

            "candidate_count":
                1000,

            "feasible_candidates":
                int(
                    len(
                        optimizer_result[
                            "feasible"
                        ]
                    )
                ),

            "baseline":
                optimizer_result["baseline"],

            "recommendation":
                recommendation,
        },

        "system": {

            "telemetry":
                "SIMULATED",

            "models":
                "XGBoost",

            "optimizer":
                "V2.1",

            "autonomous_control":
                False,
        },
    }
# ============================================================
# ENGINEER DECISION MODEL
# ============================================================

class EngineerDecisionRequest(BaseModel):
    recommendation_id: int
    decision: str
    modified_parameters: dict | None = None
    rejection_reason: str | None = None
    notes: str | None = None


# ============================================================
# ENGINEER DECISION
# ============================================================

@app.post("/api/decisions/{well_id}")
def create_engineer_decision(
    well_id: str,
    request: EngineerDecisionRequest,
):
    """
    Record an engineer decision.

    APPROVE:
        Saves approval.

    MODIFY:
        Applies engineer changes to the recommendation,
        re-runs the same ML models, and returns the new
        predicted outcome.

    REJECT:
        Saves rejection and requires a reason.
    """

    decision = request.decision.upper()

    # --------------------------------------------------------
    # Validate decision
    # --------------------------------------------------------

    if decision not in {
        "APPROVE",
        "MODIFY",
        "REJECT",
    }:
        raise HTTPException(
            status_code=400,
            detail="Decision must be APPROVE, MODIFY, or REJECT.",
        )

    # --------------------------------------------------------
    # Validate MODIFY
    # --------------------------------------------------------

    if decision == "MODIFY":

        if not request.modified_parameters:
            raise HTTPException(
                status_code=400,
                detail=(
                    "modified_parameters are required "
                    "when decision is MODIFY."
                ),
            )

    # --------------------------------------------------------
    # Validate REJECT
    # --------------------------------------------------------

    if decision == "REJECT":

        if not request.rejection_reason:
            raise HTTPException(
                status_code=400,
                detail=(
                    "rejection_reason is required "
                    "when decision is REJECT."
                ),
            )

    # --------------------------------------------------------
    # Find recommendation
    # --------------------------------------------------------

    recommendation_response = (
        supabase
        .table("recommendations")
        .select("*")
        .eq("id", request.recommendation_id)
        .eq("well_id", well_id)
        .limit(1)
        .execute()
    )

    if not recommendation_response.data:

        raise HTTPException(
            status_code=404,
            detail="Recommendation not found.",
        )

    recommendation = (
        recommendation_response.data[0]
    )

    # --------------------------------------------------------
    # MODIFY -> re-simulate engineer scenario
    # --------------------------------------------------------

    modified_simulation = None

    if decision == "MODIFY":

        # ----------------------------------------------------
        # Get latest telemetry
        # ----------------------------------------------------

        telemetry_response = (
            supabase
            .table("telemetry")
            .select("*")
            .eq("well_id", well_id)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        if not telemetry_response.data:

            raise HTTPException(
                status_code=404,
                detail=f"No telemetry found for {well_id}.",
            )

        telemetry = telemetry_response.data[0]

        # ----------------------------------------------------
        # Get static well parameters
        # ----------------------------------------------------

        well_response = (
            supabase
            .table("wells")
            .select("*")
            .eq("well_id", well_id)
            .limit(1)
            .execute()
        )

        if not well_response.data:

            raise HTTPException(
                status_code=404,
                detail=f"Well {well_id} not found.",
            )

        well = well_response.data[0]

        # ----------------------------------------------------
        # Start from optimizer recommendation
        # ----------------------------------------------------

        scenario = {

            "steam_rate":
                float(
                    recommendation["steam_rate"]
                ),

            "steam_temperature":
                float(
                    recommendation["steam_temperature"]
                ),

            "injection_pressure":
                float(
                    recommendation["injection_pressure"]
                ),

            "injection_duration":
                float(
                    recommendation["injection_duration"]
                ),

            "soak_time":
                float(
                    recommendation["soak_time"]
                ),

            "stroke_length":
                float(
                    recommendation["stroke_length"]
                ),

            "spm":
                float(
                    recommendation["spm"]
                ),

            "vfd_frequency":
                float(
                    recommendation["vfd_frequency"]
                ),
        }

        # ----------------------------------------------------
        # Apply engineer modifications
        # ----------------------------------------------------

        allowed_parameters = {
            "steam_rate",
            "steam_temperature",
            "injection_pressure",
            "injection_duration",
            "soak_time",
            "stroke_length",
            "spm",
            "vfd_frequency",
        }

        for key, value in request.modified_parameters.items():

            if key not in allowed_parameters:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported modified parameter: {key}"
                    ),
                )

            scenario[key] = float(value)

        # ----------------------------------------------------
        # If SPM changed but VFD wasn't explicitly changed,
        # derive VFD using the same relationship as Optimizer.
        # ----------------------------------------------------

        if (
            "spm" in request.modified_parameters
            and "vfd_frequency"
            not in request.modified_parameters
        ):

            scenario["vfd_frequency"] = float(
                max(
                    20.0,
                    min(
                        60.0,
                        20.0
                        + (
                            scenario["spm"]
                            / 3.0
                        )
                        * 40.0,
                    ),
                )
            )

        # ----------------------------------------------------
        # Validate operating limits
        # ----------------------------------------------------

        if (
            well.get("max_steam_rate") is not None
            and scenario["steam_rate"]
            > float(well["max_steam_rate"])
        ):

            raise HTTPException(
                status_code=400,
                detail="Steam rate exceeds the well maximum.",
            )

        if (
            well.get("min_injection_pressure") is not None
            and scenario["injection_pressure"]
            < float(well["min_injection_pressure"])
        ):

            raise HTTPException(
                status_code=400,
                detail="Injection pressure is below the well minimum.",
            )

        if (
            well.get("max_injection_pressure") is not None
            and scenario["injection_pressure"]
            > float(well["max_injection_pressure"])
        ):

            raise HTTPException(
                status_code=400,
                detail="Injection pressure exceeds the well maximum.",
            )

        if (
            well.get("min_spm") is not None
            and scenario["spm"]
            < float(well["min_spm"])
        ):

            raise HTTPException(
                status_code=400,
                detail="SPM is below the well minimum.",
            )

        if (
            well.get("max_spm") is not None
            and scenario["spm"]
            > float(well["max_spm"])
        ):

            raise HTTPException(
                status_code=400,
                detail="SPM exceeds the well maximum.",
            )

        if (
            well.get("min_stroke_length") is not None
            and scenario["stroke_length"]
            < float(well["min_stroke_length"])
        ):

            raise HTTPException(
                status_code=400,
                detail="Stroke length is below the well minimum.",
            )

        if (
            well.get("max_stroke_length") is not None
            and scenario["stroke_length"]
            > float(well["max_stroke_length"])
        ):

            raise HTTPException(
                status_code=400,
                detail="Stroke length exceeds the well maximum.",
            )

        if (
            well.get("min_vfd_frequency") is not None
            and scenario["vfd_frequency"]
            < float(well["min_vfd_frequency"])
        ):

            raise HTTPException(
                status_code=400,
                detail="VFD frequency is below the well minimum.",
            )

        if (
            well.get("max_vfd_frequency") is not None
            and scenario["vfd_frequency"]
            > float(well["max_vfd_frequency"])
        ):

            raise HTTPException(
                status_code=400,
                detail="VFD frequency exceeds the well maximum.",
            )

        # ----------------------------------------------------
        # Build ML input
        # ----------------------------------------------------

        scenario_raw = telemetry.copy()

        scenario_raw["api_gravity"] = well.get(
            "api_gravity",
            0.0,
        )

        scenario_raw["asphaltene_content"] = well.get(
            "asphaltene_content",
            0.0,
        )

        # ----------------------------------------------------
        # Apply modified operating parameters
        # ----------------------------------------------------

        for key, value in scenario.items():

            scenario_raw[key] = value

        # ----------------------------------------------------
        # Steam volume
        # Same calculation as Optimizer V2.1
        # ----------------------------------------------------

        scenario_raw["steam_volume"] = (
            scenario["steam_rate"]
            * scenario["injection_duration"]
            * 24.0
        )

        # ----------------------------------------------------
        # Mechanical state
        # ----------------------------------------------------

        (
            rod_load,
            pump_load,
            pump_fillage,
        ) = calculate_mechanical_state(
            float(
                scenario_raw["oil_viscosity"]
            ),
            float(
                scenario_raw["reservoir_pressure"]
            ),
            scenario["spm"],
        )

        scenario_raw["rod_load"] = float(
            rod_load
        )

        scenario_raw["pump_load"] = float(
            pump_load
        )

        scenario_raw["pump_fillage"] = float(
            pump_fillage
        )

        # ----------------------------------------------------
        # Energy
        # ----------------------------------------------------

        scenario_energy = float(
            calculate_energy(
                scenario["vfd_frequency"],
                float(pump_load),
            )
        )

        scenario_raw["current_energy"] = (
            scenario_energy
        )

        # ----------------------------------------------------
        # Predict modified scenario
        # ----------------------------------------------------

        scenario_df = pd.DataFrame(
            [scenario_raw]
        )

        (
            predicted_temperature,
            predicted_oil_rate,
            predicted_rod_risk,
        ) = batch_predict(
            scenario_df
        )

        predicted_temperature = float(
            predicted_temperature[0]
        )

        predicted_oil_rate = float(
            predicted_oil_rate[0]
        )

        predicted_rod_risk_pct = float(
            predicted_rod_risk[0] * 100.0
        )

        # ----------------------------------------------------
        # Baseline prediction
        # ----------------------------------------------------

        baseline_raw = telemetry.copy()

        baseline_raw["api_gravity"] = well.get(
            "api_gravity",
            0.0,
        )

        baseline_raw["asphaltene_content"] = well.get(
            "asphaltene_content",
            0.0,
        )

        baseline_df = pd.DataFrame(
            [baseline_raw]
        )

        (
            baseline_temperature,
            baseline_oil_rate,
            baseline_rod_risk,
        ) = batch_predict(
            baseline_df
        )

        baseline_temperature = float(
            baseline_temperature[0]
        )

        baseline_oil_rate = float(
            baseline_oil_rate[0]
        )

        baseline_rod_risk_pct = float(
            baseline_rod_risk[0] * 100.0
        )

        baseline_energy = float(
            telemetry["current_energy"]
        )

        # ----------------------------------------------------
        # Calculate changes
        # ----------------------------------------------------

        oil_change_pct = (
            (
                predicted_oil_rate
                - baseline_oil_rate
            )
            / max(
                abs(baseline_oil_rate),
                1e-9,
            )
        ) * 100.0

        risk_change_pct = (
            (
                predicted_rod_risk_pct
                - baseline_rod_risk_pct
            )
            / max(
                abs(baseline_rod_risk_pct),
                1e-9,
            )
        ) * 100.0

        energy_change_pct = (
            (
                scenario_energy
                - baseline_energy
            )
            / max(
                abs(baseline_energy),
                1e-9,
            )
        ) * 100.0

        sor_proxy = (
            scenario_raw["steam_volume"]
            / max(
                predicted_oil_rate,
                1.0,
            )
        )

        rod_status = (
            "FLOATING RISK"
            if predicted_rod_risk[0]
            >= rod_threshold
            else "NORMAL"
        )

        # ----------------------------------------------------
        # Modified simulation result
        # ----------------------------------------------------

        modified_simulation = {

            "simulation_type":
                "ENGINEER_MODIFIED",

            "saved_to_database":
                False,

            "modified_parameters":
                scenario,

            "predicted_outcome": {

                "temperature":
                    predicted_temperature,

                "oil_rate":
                    predicted_oil_rate,

                "rod_risk_pct":
                    predicted_rod_risk_pct,

                "rod_status":
                    rod_status,

                "energy":
                    scenario_energy,

                "sor_proxy":
                    float(sor_proxy),
            },

            "changes_vs_baseline": {

                "oil_change_pct":
                    oil_change_pct,

                "risk_change_pct":
                    risk_change_pct,

                "energy_change_pct":
                    energy_change_pct,
            },
        }

    # --------------------------------------------------------
    # Save engineer decision
    # --------------------------------------------------------

    decision_row = {

        "well_id":
            well_id,

        "recommendation_id":
            request.recommendation_id,

        "decision":
            decision,

        "modified_parameters":
            request.modified_parameters,

        "rejection_reason":
            request.rejection_reason,

        "notes":
            request.notes,
    }

    decision_response = (
        supabase
        .table("engineer_decisions")
        .insert(decision_row)
        .execute()
    )

    if not decision_response.data:

        raise HTTPException(
            status_code=500,
            detail="Failed to save engineer decision.",
        )

    saved_decision = (
        decision_response.data[0]
    )

    # --------------------------------------------------------
    # Return result
    # --------------------------------------------------------

    return {

        "status":
            "RECORDED",

        "well_id":
            well_id,

        "recommendation_id":
            request.recommendation_id,

        "decision_id":
            saved_decision["id"],

        "decision":
            decision,

        "modified_simulation":
            modified_simulation,

        "recommendation":
            recommendation,
    }
@app.get("/api/decisions/history/{well_id}")
def get_decision_history(well_id: str):
    # Get all engineer decisions for this well
    decisions_response = (
        supabase
        .table("engineer_decisions")
        .select(
            "id,well_id,recommendation_id,engineer_id,"
            "decision,modified_parameters,rejection_reason,"
            "notes,created_at"
        )
        .eq("well_id", well_id)
        .order("created_at", desc=True)
        .execute()
    )

    decisions = decisions_response.data or []

    if not decisions:
        return {
            "well_id": well_id,
            "count": 0,
            "history": []
        }

    # Collect recommendation IDs linked to those decisions
    recommendation_ids = list({
        decision["recommendation_id"]
        for decision in decisions
        if decision.get("recommendation_id") is not None
    })

    recommendations = {}

    if recommendation_ids:
        recommendations_response = (
            supabase
            .table("recommendations")
            .select(
                "id,well_id,prediction_id,created_at,"
                "steam_rate,steam_temperature,"
                "injection_pressure,injection_duration,"
                "soak_time,steam_volume,"
                "stroke_length,spm,vfd_frequency,"
                "predicted_reservoir_temperature,"
                "predicted_oil_rate,"
                "predicted_rod_risk_pct,"
                "predicted_energy,"
                "sor_proxy,"
                "optimization_score,"
                "oil_change_pct,"
                "risk_change_pct,"
                "energy_change_pct,"
                "optimizer_status,"
                "candidate_count,"
                "feasible_candidate_count,"
                "optimizer_version"
            )
            .in_("id", recommendation_ids)
            .execute()
        )

        for recommendation in (recommendations_response.data or []):
            recommendations[recommendation["id"]] = recommendation

    # Build history records
    history = []

    for decision in decisions:
        recommendation_id = decision.get("recommendation_id")

        history.append({
            "decision_id": decision["id"],
            "well_id": decision["well_id"],
            "recommendation_id": recommendation_id,
            "engineer_id": decision.get("engineer_id"),
            "decision": decision["decision"],
            "modified_parameters": decision.get("modified_parameters"),
            "rejection_reason": decision.get("rejection_reason"),
            "notes": decision.get("notes"),
            "created_at": decision["created_at"],
            "recommendation": recommendations.get(recommendation_id)
        })

    return {
        "well_id": well_id,
        "count": len(history),
        "history": history
    }