from pathlib import Path

import pandas as pd

from app.supabase_client import supabase


BASE_DIR = Path("/mnt/d/Final sih/backend")
DATASET = BASE_DIR / "data" / "baghewala_synthetic_v1_corrected.csv"


print("\n" + "=" * 60)
print("WELLWISE — SEEDING WELLS")
print("=" * 60)


# ------------------------------------------------------------
# Load dataset
# ------------------------------------------------------------

df = pd.read_csv(DATASET)

required_columns = [
    "well_id",
    "api_gravity",
    "asphaltene_content",
]

missing = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing:
    raise ValueError(
        f"Missing dataset columns: {missing}"
    )


# ------------------------------------------------------------
# Get one static record per well
# ------------------------------------------------------------

wells_df = (
    df[
        [
            "well_id",
            "api_gravity",
            "asphaltene_content",
        ]
    ]
    .drop_duplicates(subset=["well_id"])
    .sort_values("well_id")
)


# ------------------------------------------------------------
# Build Supabase records
# ------------------------------------------------------------

records = []

for _, row in wells_df.iterrows():

    def clean_number(value):
        if pd.isna(value):
            return None
        return float(value)

    records.append(
        {
            "well_id": str(row["well_id"]),
            "field_name": "Baghewala",
            "basin_name": None,
            "reservoir_name": "Baghewala Heavy Oil Reservoir",
            "formation_name": "Jodhpur Sandstone",
            "api_gravity": clean_number(
                row["api_gravity"]
            ),
            "asphaltene_content": clean_number(
                row["asphaltene_content"]
            ),
            "well_status": "ACTIVE",

            # Engineering operating limits will be
            # defined later; don't invent them here.
            "max_steam_rate": None,
            "min_injection_pressure": None,
            "max_injection_pressure": None,
            "min_spm": None,
            "max_spm": None,
            "min_stroke_length": None,
            "max_stroke_length": None,
            "min_vfd_frequency": None,
            "max_vfd_frequency": None,
        }
    )


# ------------------------------------------------------------
# Insert / update wells
# ------------------------------------------------------------

if not records:
    raise RuntimeError("No wells found in dataset")


response = (
    supabase
    .table("wells")
    .upsert(records)
    .execute()
)


# ------------------------------------------------------------
# Verify
# ------------------------------------------------------------

verify = (
    supabase
    .table("wells")
    .select("well_id, api_gravity, asphaltene_content")
    .order("well_id")
    .execute()
)


print("\n✅ Wells seeded successfully")
print("Rows returned:", len(verify.data))

print("\nWELLS")
print("-" * 60)

for well in verify.data:
    print(
        f"{well['well_id']}  |  "
        f"API: {well['api_gravity']}  |  "
        f"Asphaltene: {well['asphaltene_content']}"
    )

print("\n" + "=" * 60)
print("✅ WELL SEEDING COMPLETE")
print("=" * 60)
