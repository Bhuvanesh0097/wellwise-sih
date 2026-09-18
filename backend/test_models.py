from pathlib import Path
import joblib
import pandas as pd

BASE_DIR = Path("/mnt/d/Final sih/backend")
MODEL_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"

print("\n" + "=" * 60)
print("WELLWISE ML MODEL LOADING TEST")
print("=" * 60)

# Load models
model1 = joblib.load(MODEL_DIR / "model1_final.pkl")
model2 = joblib.load(MODEL_DIR / "model2_final.pkl")
model3 = joblib.load(MODEL_DIR / "model3_final.pkl")

print("\n✅ Model 1 loaded:", type(model1).__name__)
print("✅ Model 2 loaded:", type(model2).__name__)
print("✅ Model 3 loaded:", type(model3).__name__)

# Load preprocessors
preprocessor1 = joblib.load(MODEL_DIR / "model1_preprocessor.pkl")
preprocessor2 = joblib.load(MODEL_DIR / "model2_preprocessor.pkl")
preprocessor3 = joblib.load(MODEL_DIR / "model3_preprocessor.pkl")

print("\n✅ Preprocessor 1 loaded:", type(preprocessor1).__name__)
print("✅ Preprocessor 2 loaded:", type(preprocessor2).__name__)
print("✅ Preprocessor 3 loaded:", type(preprocessor3).__name__)

# Load feature lists
features1 = joblib.load(MODEL_DIR / "model1_features.pkl")
features2 = joblib.load(MODEL_DIR / "model2_features.pkl")
features3 = joblib.load(MODEL_DIR / "model3_features.pkl")

print("\nFeature counts:")
print("Model 1:", len(features1))
print("Model 2:", len(features2))
print("Model 3:", len(features3))

# Load dataset
dataset_path = DATA_DIR / "baghewala_synthetic_v1_corrected.csv"
df = pd.read_csv(dataset_path)

print("\n✅ Dataset loaded")
print("Rows:", len(df))
print("Columns:", len(df.columns))
print("Wells:", df["well_id"].nunique())

print(
    "Time range:",
    df["timestamp"].min(),
    "→",
    df["timestamp"].max()
)

print("\n" + "=" * 60)
print("WELLWISE ML ARTIFACT TEST PASSED")
print("=" * 60)

