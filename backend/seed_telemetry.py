from pathlib import Path
import pandas as pd

from app.supabase_client import supabase


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATASET = (
    BASE_DIR
    / "data"
    / "baghewala_synthetic_v1_corrected.csv"
)


print("\n" + "=" * 60)
print("WELLWISE — SEEDING INITIAL TELEMETRY")
print("=" * 60)


# ============================================================
# LOAD DATASET
# ============================================================

df = pd.read_csv(DATASET)

df["timestamp"] = pd.to_datetime(df["timestamp"])


# ============================================================
# SELECT LATEST RECORD FOR EACH WELL
# ============================================================

latest_df = (
    df.sort_values("timestamp")
    .groupby("well_id", as_index=False)
    .tail(1)
    .sort_values("well_id")
    .reset_index(drop=True)
)


print(f"\nFound {len(latest_df)} latest well states.")


# ============================================================
# TELEMETRY COLUMNS
# ============================================================

telemetry_columns = [
    "well_id",
    "timestamp",
    "css_cycle_id",
    "cycle_day",
    "cycle_phase",
    "reservoir_pressure",
    "reservoir_temperature",
    "oil_viscosity",
    "steam_rate",
    "steam_volume",
    "steam_temperature",
    "injection_pressure",
    "injection_duration",
    "soak_time",
    "days_since_previous_css",
    "stroke_length",
    "spm",
    "vfd_frequency",
    "rod_load",
    "pump_load",
    "pump_fillage",
    "current_oil_rate",
    "current_water_rate",
    "current_energy",
    "fluid_level",
]


# ============================================================
# CHECK REQUIRED COLUMNS
# ============================================================

missing = [
    column
    for column in telemetry_columns
    if column not in latest_df.columns
]

if missing:
    raise ValueError(
        f"Missing telemetry columns: {missing}"
    )


# ============================================================
# CONVERT DATASET ROWS → SUPABASE RECORDS
# ============================================================

def clean_value(value):

    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    # Convert NumPy numeric values to normal Python values
    if hasattr(value, "item"):
        return value.item()

    return value


records = []

for _, row in latest_df.iterrows():

    record = {
        column: clean_value(row[column])
        for column in telemetry_columns
    }

    # This dataset is currently our simulated source.
    record["source"] = "SIMULATED"

    records.append(record)


# ============================================================
# INSERT INTO SUPABASE
# ============================================================

response = (
    supabase
    .table("telemetry")
    .upsert(
        records,
        on_conflict="well_id,timestamp"
    )
    .execute()
)


# ============================================================
# VERIFY
# ============================================================

verify = (
    supabase
    .table("telemetry")
    .select(
        "well_id, timestamp, reservoir_temperature, "
        "current_oil_rate, spm, vfd_frequency, source"
    )
    .order("well_id")
    .execute()
)


print("\n✅ Telemetry seeded successfully")
print("Rows returned:", len(verify.data))

print("\nLATEST WELL TELEMETRY")
print("-" * 60)

for row in verify.data:

    print(
        f"{row['well_id']} | "
        f"{row['timestamp']} | "
        f"Temp: {row['reservoir_temperature']} °C | "
        f"Oil: {row['current_oil_rate']} BOPD | "
        f"SPM: {row['spm']} | "
        f"VFD: {row['vfd_frequency']} Hz | "
        f"Source: {row['source']}"
    )


print("\n" + "=" * 60)
print("✅ INITIAL TELEMETRY SEEDING COMPLETE")
print("=" * 60)
