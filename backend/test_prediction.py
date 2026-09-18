from pathlib import Path
import json
import joblib
import pandas as pd

BASE_DIR = Path("/mnt/d/Final sih/backend")
MODEL_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"

# --------------------------------------------------
# Load models
# --------------------------------------------------

model1 = joblib.load(MODEL_DIR / "model1_final.pkl")
model2 = joblib.load(MODEL_DIR / "model2_final.pkl")
model3 = joblib.load(MODEL_DIR / "model3_final.pkl")

# --------------------------------------------------
# Load preprocessors
# --------------------------------------------------

encoder1 = joblib.load(MODEL_DIR / "model1_preprocessor.pkl")
encoder2 = joblib.load(MODEL_DIR / "model2_preprocessor.pkl")
encoder3 = joblib.load(MODEL_DIR / "model3_preprocessor.pkl")

# --------------------------------------------------
# Load feature lists
# --------------------------------------------------

features1 = joblib.load(MODEL_DIR / "model1_features.pkl")
features2 = joblib.load(MODEL_DIR / "model2_features.pkl")
features3 = joblib.load(MODEL_DIR / "model3_features.pkl")

# --------------------------------------------------
# Load Model 3 threshold
# --------------------------------------------------

with open(MODEL_DIR / "model3_metadata.json", "r") as f:
    metadata = json.load(f)

rod_threshold = float(metadata["threshold"])

# --------------------------------------------------
# Load dataset
# --------------------------------------------------

df = pd.read_csv(
    DATA_DIR / "baghewala_synthetic_v1_corrected.csv"
)

df["timestamp"] = pd.to_datetime(df["timestamp"])

# IMPORTANT:
# These 3 features were created during model training.
df["hour"] = df["timestamp"].dt.hour
df["day_of_week"] = df["timestamp"].dt.dayofweek
df["month"] = df["timestamp"].dt.month


# --------------------------------------------------
# Exact feature preparation used by the notebook
# --------------------------------------------------

def prepare_model_matrix(scenario_df, encoder, feature_list):

    data = scenario_df.copy()

    if "cycle_phase" in data.columns:

        encoded = encoder.transform(
            data[["cycle_phase"]]
        )

        encoded_columns = [
            f"cycle_phase_{cat}"
            for cat in encoder.categories_[0]
        ]

        encoded_df = pd.DataFrame(
            encoded,
            columns=encoded_columns,
            index=data.index
        )

        data = data.drop(
            columns=["cycle_phase"]
        )

        data = pd.concat(
            [data, encoded_df],
            axis=1
        )

    for col in feature_list:

        if col not in data.columns:
            data[col] = 0.0

    return data[feature_list]


# --------------------------------------------------
# Select one real well
# --------------------------------------------------

well_id = "BGW_01"

well_data = (
    df[df["well_id"] == well_id]
    .sort_values("timestamp")
)

if well_data.empty:
    raise ValueError(f"{well_id} not found")

current = well_data.iloc[-1].copy()

current_df = pd.DataFrame([current])


# --------------------------------------------------
# Prepare input for all 3 models
# --------------------------------------------------

X1 = prepare_model_matrix(
    current_df,
    encoder1,
    features1
)

X2 = prepare_model_matrix(
    current_df,
    encoder2,
    features2
)

X3 = prepare_model_matrix(
    current_df,
    encoder3,
    features3
)

print("\nFEATURE MATRIX SHAPES")
print("-----------------------------")
print("Model 1:", X1.shape)
print("Model 2:", X2.shape)
print("Model 3:", X3.shape)


# --------------------------------------------------
# Predictions
# --------------------------------------------------

temperature_prediction = float(
    model1.predict(X1)[0]
)

oil_prediction = float(
    model2.predict(X2)[0]
)

rod_probability = float(
    model3.predict_proba(X3)[0, 1]
)

rod_risk_percent = rod_probability * 100

rod_status = (
    "FLOATING RISK"
    if rod_probability >= rod_threshold
    else "NORMAL"
)


# --------------------------------------------------
# Display
# --------------------------------------------------

print("\n" + "=" * 60)
print("WELLWISE DIGITAL TWIN — REAL MODEL PREDICTION TEST")
print("=" * 60)

print("\nCURRENT WELL")
print("-----------------------------")
print("Well ID:", well_id)
print("Timestamp:", current["timestamp"])
print(
    f"Reservoir temperature: "
    f"{current['reservoir_temperature']:.2f} °C"
)
print(
    f"Reservoir pressure: "
    f"{current['reservoir_pressure']:.2f}"
)
print(
    f"Current oil rate: "
    f"{current['current_oil_rate']:.2f} BOPD"
)
print(
    f"SPM: "
    f"{current['spm']:.2f}"
)
print(
    f"Stroke length: "
    f"{current['stroke_length']:.2f} in"
)
print(
    f"VFD: "
    f"{current['vfd_frequency']:.2f} Hz"
)

print("\nAI 24-HOUR PREDICTIONS")
print("-----------------------------")
print(
    f"Future reservoir temperature: "
    f"{temperature_prediction:.2f} °C"
)
print(
    f"Future oil rate: "
    f"{oil_prediction:.2f} BOPD"
)
print(
    f"Rod floating probability: "
    f"{rod_probability:.4f}"
)
print(
    f"Rod floating risk: "
    f"{rod_risk_percent:.2f}%"
)
print(
    f"Rod status: "
    f"{rod_status}"
)

print("\n" + "=" * 60)
print("✅ REAL XGBOOST INFERENCE TEST PASSED")
print("=" * 60)
