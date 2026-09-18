from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"


# ============================================================
# LOAD FINAL SAVED ARTIFACTS
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

encoder1 = joblib.load(
    MODEL_DIR / "model1_preprocessor.pkl"
)

encoder2 = joblib.load(
    MODEL_DIR / "model2_preprocessor.pkl"
)

encoder3 = joblib.load(
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
# MODEL 3 THRESHOLD
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
# FAST BATCH FEATURE MATRIX
# ============================================================

def prepare_model_matrix(
    scenario_df: pd.DataFrame,
    encoder,
    feature_list,
) -> pd.DataFrame:

    data = scenario_df.copy()

    # --------------------------------------------------------
    # Timestamp-derived features
    #
    # These were already part of the original training pipeline.
    # --------------------------------------------------------

    if "timestamp" in data.columns:

        data["timestamp"] = pd.to_datetime(
            data["timestamp"]
        )

        data["hour"] = (
            data["timestamp"].dt.hour
        )

        data["day_of_week"] = (
            data["timestamp"].dt.dayofweek
        )

        data["month"] = (
            data["timestamp"].dt.month
        )

    # --------------------------------------------------------
    # Encode cycle phase
    # --------------------------------------------------------

    if "cycle_phase" in data.columns:

        encoded = encoder.transform(
            data[["cycle_phase"]]
        )

        encoded_columns = [
            f"cycle_phase_{category}"
            for category in encoder.categories_[0]
        ]

        encoded_df = pd.DataFrame(
            encoded,
            columns=encoded_columns,
            index=data.index,
        )

        data = data.drop(
            columns=["cycle_phase"]
        )

        data = pd.concat(
            [data, encoded_df],
            axis=1,
        )

    # --------------------------------------------------------
    # Add any missing expected columns
    # --------------------------------------------------------

    for column in feature_list:

        if column not in data.columns:

            data[column] = 0.0

    # --------------------------------------------------------
    # Exact training feature order
    # --------------------------------------------------------

    data = data[
        feature_list
    ]

    return data.astype(float)


# ============================================================
# FAST BATCH PREDICTION
# ============================================================

def batch_predict(
    scenario_df: pd.DataFrame
):

    X1 = prepare_model_matrix(
        scenario_df,
        encoder1,
        features1,
    )

    X2 = prepare_model_matrix(
        scenario_df,
        encoder2,
        features2,
    )

    X3 = prepare_model_matrix(
        scenario_df,
        encoder3,
        features3,
    )

    temperature = model1.predict(
        X1
    )

    oil_rate = model2.predict(
        X2
    )

    rod_probability = model3.predict_proba(
        X3
    )[:, 1]

    return (
        temperature,
        oil_rate,
        rod_probability,
    )


# ============================================================
# MECHANICAL STATE CALCULATION
# ============================================================

def calculate_mechanical_state(
    viscosity,
    pressure,
    spm,
):

    viscosity_factor = np.log1p(
        viscosity / 5000.0
    )

    rod_load = np.clip(
        5.0
        + 3.0 * (spm / 3.2)
        + 2.0 * viscosity_factor,
        3.0,
        20.0,
    )

    pump_load = np.clip(
        32.0
        + 28.0 * (spm / 3.2)
        + 8.0 * (viscosity / 13000.0),
        30.0,
        95.0,
    )

    pump_fillage = np.clip(
        96.0
        - 18.0 * (spm / 3.2) ** 1.7
        - 14.0 * (viscosity / 13000.0)
        + 7.0 * (pressure / 50.0),
        25.0,
        100.0,
    )

    return (
        rod_load,
        pump_load,
        pump_fillage,
    )


# ============================================================
# ENERGY PROXY
# ============================================================

def calculate_energy(
    vfd,
    pump_load,
):

    pump_power_kw = (
        4.0
        + 18.0
        * (vfd / 60.0) ** 2
        * (0.55 + pump_load / 100.0)
    )

    return (
        np.clip(
            pump_power_kw,
            3.0,
            30.0,
        )
        * 24.0
    )


# ============================================================
# OPTIMIZER SETTINGS
# ============================================================

N_CANDIDATES = 1000

# Keep the optimizer behavior aligned with
# the verified notebook implementation.
rng = np.random.default_rng(42)


# ============================================================
# ONE-WELL CSS + SRP OPTIMIZER
# ============================================================

def optimize_well_fast(
    current_raw: pd.Series,
    n_candidates: int = N_CANDIDATES,
):

    # ========================================================
    # 1. BASELINE PREDICTION
    # ========================================================

    baseline_df = pd.DataFrame(
        [current_raw.to_dict()]
    )

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

    baseline_risk = float(
        baseline_risk[0] * 100.0
    )

    baseline_energy = float(
        current_raw["current_energy"]
    )

    # ========================================================
    # 2. CREATE CANDIDATE DATAFRAME
    # ========================================================

    base_dict = (
        current_raw.to_dict()
    )

    scenario_df = pd.DataFrame(
        [base_dict] * n_candidates
    ).reset_index(
        drop=True
    )

    # ========================================================
    # 3. CSS SETTINGS
    # ========================================================

    scenario_df["steam_rate"] = rng.choice(
        [
            1.2,
            2.0,
            3.0,
            4.0,
            5.0,
            6.0,
        ],
        n_candidates,
    )

    scenario_df["steam_temperature"] = rng.choice(
        [
            250,
            270,
            290,
            310,
            330,
            340,
        ],
        n_candidates,
    )

    scenario_df["injection_pressure"] = rng.choice(
        [
            150,
            155,
            162.5,
            170,
            175,
        ],
        n_candidates,
    )

    scenario_df["injection_duration"] = rng.choice(
        [
            14,
            18,
            21,
        ],
        n_candidates,
    )

    scenario_df["soak_time"] = rng.choice(
        [
            24,
            48,
            72,
            96,
        ],
        n_candidates,
    )

    # ========================================================
    # 4. SRP SETTINGS
    # ========================================================

    scenario_df["stroke_length"] = rng.choice(
        [
            61,
            74,
            86,
        ],
        n_candidates,
    )

    scenario_df["spm"] = rng.choice(
        [
            1.0,
            1.25,
            1.5,
            1.75,
            2.0,
            2.25,
            2.5,
            2.75,
            3.0,
        ],
        n_candidates,
    )

    scenario_df["vfd_frequency"] = np.clip(
        20.0
        + (
            scenario_df["spm"].to_numpy()
            / 3.0
        )
        * 40.0,
        20.0,
        60.0,
    )

    # ========================================================
    # 5. STEAM VOLUME
    # ========================================================

    scenario_df["steam_volume"] = (
        scenario_df["steam_rate"]
        * scenario_df["injection_duration"]
        * 24.0
    )

    # ========================================================
    # 6. MECHANICAL VARIABLES
    # ========================================================

    viscosity = (
        scenario_df[
            "oil_viscosity"
        ]
        .to_numpy()
    )

    pressure = (
        scenario_df[
            "reservoir_pressure"
        ]
        .to_numpy()
    )

    spm = (
        scenario_df[
            "spm"
        ]
        .to_numpy()
    )

    (
        rod_load,
        pump_load,
        pump_fillage,
    ) = calculate_mechanical_state(
        viscosity,
        pressure,
        spm,
    )

    scenario_df["rod_load"] = (
        rod_load
    )

    scenario_df["pump_load"] = (
        pump_load
    )

    scenario_df["pump_fillage"] = (
        pump_fillage
    )

    # ========================================================
    # 7. ENERGY
    # ========================================================

    vfd = (
        scenario_df[
            "vfd_frequency"
        ]
        .to_numpy()
    )

    energy = calculate_energy(
        vfd,
        pump_load,
    )

    scenario_df["current_energy"] = (
        energy
    )

    # ========================================================
    # 8. BATCH ML PREDICTION
    # ========================================================

    (
        pred_temp,
        pred_oil,
        pred_risk,
    ) = batch_predict(
        scenario_df
    )

    pred_risk_pct = (
        pred_risk * 100.0
    )

    # ========================================================
    # 9. PERFORMANCE METRICS
    # ========================================================

    oil_change_pct = (
        (
            pred_oil
            - baseline_oil
        )
        / max(
            abs(baseline_oil),
            1e-9,
        )
    ) * 100.0

    risk_change_pct = (
        (
            pred_risk_pct
            - baseline_risk
        )
        / max(
            abs(baseline_risk),
            1e-9,
        )
    ) * 100.0

    energy_change_pct = (
        (
            energy
            - baseline_energy
        )
        / max(
            abs(baseline_energy),
            1e-9,
        )
    ) * 100.0

    # ========================================================
    # 10. SOR PROXY
    # ========================================================

    sor_proxy = (
        scenario_df[
            "steam_volume"
        ].to_numpy()
        / np.maximum(
            pred_oil,
            1.0,
        )
    )

    # ========================================================
    # 11. BUILD CANDIDATE TABLE
    # ========================================================

    candidates = pd.DataFrame({

        "steam_rate":
            scenario_df[
                "steam_rate"
            ].to_numpy(),

        "steam_temperature":
            scenario_df[
                "steam_temperature"
            ].to_numpy(),

        "injection_pressure":
            scenario_df[
                "injection_pressure"
            ].to_numpy(),

        "injection_duration":
            scenario_df[
                "injection_duration"
            ].to_numpy(),

        "soak_time":
            scenario_df[
                "soak_time"
            ].to_numpy(),

        "steam_volume":
            scenario_df[
                "steam_volume"
            ].to_numpy(),

        "stroke_length":
            scenario_df[
                "stroke_length"
            ].to_numpy(),

        "spm":
            scenario_df[
                "spm"
            ].to_numpy(),

        "vfd_frequency":
            scenario_df[
                "vfd_frequency"
            ].to_numpy(),

        "pred_temperature":
            pred_temp,

        "pred_oil":
            pred_oil,

        "rod_risk":
            pred_risk_pct,

        "energy":
            energy,

        "sor_proxy":
            sor_proxy,

        "oil_change_pct":
            oil_change_pct,

        "risk_change_pct":
            risk_change_pct,

        "energy_change_pct":
            energy_change_pct,
    })

    # ========================================================
    # 12. HARD CONSTRAINTS
    #
    # Production cannot fall more than 1%
    # Energy cannot increase more than 15%
    # Rod-floating risk must decrease
    # ========================================================

    feasible = candidates[
        (candidates["oil_change_pct"] >= -1.0)
        &
        (candidates["energy_change_pct"] <= 15.0)
        &
        (candidates["risk_change_pct"] < 0.0)
    ].copy()

    # ========================================================
    # 13. NO FEASIBLE CANDIDATE
    # ========================================================

    if len(feasible) == 0:

        return {
            "status": "NO_FEASIBLE_CANDIDATE",

            "baseline": {
                "temperature":
                    baseline_temp,

                "oil":
                    baseline_oil,

                "risk":
                    baseline_risk,

                "energy":
                    baseline_energy,
            },

            "candidates":
                candidates,

            "feasible":
                feasible,

            "recommended":
                None,
        }

    # ========================================================
    # 14. NORMALIZATION
    # ========================================================

    def normalize(series):

        low = series.min()
        high = series.max()

        if high == low:

            return pd.Series(
                0.5,
                index=series.index,
            )

        return (
            (series - low)
            / (high - low)
        )

    feasible["oil_score"] = normalize(
        feasible[
            "oil_change_pct"
        ]
    )

    feasible["risk_score"] = normalize(
        -feasible[
            "risk_change_pct"
        ]
    )

    feasible["energy_score"] = normalize(
        -feasible[
            "energy_change_pct"
        ]
    )

    feasible["steam_score"] = normalize(
        -feasible[
            "sor_proxy"
        ]
    )

    # ========================================================
    # 15. OPTIMIZATION SCORE
    #
    # Same verified notebook weighting:
    #
    # Oil       = 40%
    # Risk      = 35%
    # Energy    = 15%
    # Steam/SOR = 10%
    # ========================================================

    feasible["optimization_score"] = (

        0.40
        * feasible["oil_score"]

        + 0.35
        * feasible["risk_score"]

        + 0.15
        * feasible["energy_score"]

        + 0.10
        * feasible["steam_score"]
    )

    # ========================================================
    # 16. SORT AND SELECT RECOMMENDATION
    # ========================================================

    feasible = (
        feasible
        .sort_values(
            "optimization_score",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    recommended = feasible.iloc[0]

    # ========================================================
    # 17. RETURN RESULT
    # ========================================================

    return {

        "status": "FEASIBLE",

        "baseline": {
            "temperature":
                baseline_temp,

            "oil":
                baseline_oil,

            "risk":
                baseline_risk,

            "energy":
                baseline_energy,
        },

        "candidates":
            candidates,

        "feasible":
            feasible,

        "recommended":
            recommended,
    }
