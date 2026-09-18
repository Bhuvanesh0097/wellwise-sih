import pandas as pd
from app.supabase_client import supabase
from app.optimizer import optimize_well_fast


WELL_ID = "BGW_01"


# ------------------------------------------------------------
# Get latest telemetry
# ------------------------------------------------------------

telemetry_response = (
    supabase
    .table("telemetry")
    .select("*")
    .eq("well_id", WELL_ID)
    .order("timestamp", desc=True)
    .limit(1)
    .execute()
)

if not telemetry_response.data:
    raise RuntimeError(
        f"No telemetry found for {WELL_ID}"
    )

telemetry = telemetry_response.data[0]


# ------------------------------------------------------------
# Get static well information
# ------------------------------------------------------------

well_response = (
    supabase
    .table("wells")
    .select("*")
    .eq("well_id", WELL_ID)
    .limit(1)
    .execute()
)

if not well_response.data:
    raise RuntimeError(
        f"No well configuration found for {WELL_ID}"
    )

well = well_response.data[0]


# ------------------------------------------------------------
# Combine dynamic telemetry + static well parameters
# ------------------------------------------------------------

current_raw = telemetry.copy()

current_raw["api_gravity"] = well.get(
    "api_gravity",
    0.0
)

current_raw["asphaltene_content"] = well.get(
    "asphaltene_content",
    0.0
)
current_raw = pd.Series(current_raw)

# ------------------------------------------------------------
# Run optimizer
# ------------------------------------------------------------

print("=" * 70)
print("WELLWISE OPTIMIZER TEST")
print("=" * 70)

print(f"Well ID          : {WELL_ID}")
print(f"Telemetry time    : {current_raw.get('timestamp')}")
print(f"Current oil rate  : {current_raw.get('current_oil_rate')}")
print(f"Current temperature: {current_raw.get('reservoir_temperature')}")
print(f"Current pressure  : {current_raw.get('reservoir_pressure')}")
print(f"Current SPM       : {current_raw.get('spm')}")
print()

print("Running 1,000 candidate simulations...")
print()


result = optimize_well_fast(
    current_raw,
    n_candidates=1000
)


# ------------------------------------------------------------
# Print baseline
# ------------------------------------------------------------

print("=" * 70)
print("BASELINE")
print("=" * 70)

baseline = result["baseline"]

print(
    f"Predicted temperature : "
    f"{baseline['temperature']:.2f} °C"
)

print(
    f"Predicted oil rate    : "
    f"{baseline['oil']:.2f} BOPD"
)

print(
    f"Rod floating risk     : "
    f"{baseline['risk']:.2f}%"
)

print(
    f"Energy                : "
    f"{baseline['energy']:.2f}"
)

print()


# ------------------------------------------------------------
# Print optimizer result
# ------------------------------------------------------------

print("=" * 70)
print("OPTIMIZER RESULT")
print("=" * 70)

print(
    f"Status               : "
    f"{result['status']}"
)

print(
    f"Total candidates     : "
    f"{len(result['candidates'])}"
)

print(
    f"Feasible candidates  : "
    f"{len(result['feasible'])}"
)

print()


# ------------------------------------------------------------
# Recommended operating point
# ------------------------------------------------------------

recommended = result["recommended"]

if recommended is None:

    print(
        "No feasible operating point was found."
    )

else:

    print("=" * 70)
    print("RECOMMENDED CSS + SRP SETTINGS")
    print("=" * 70)

    print(
        f"Steam rate          : "
        f"{recommended['steam_rate']:.2f}"
    )

    print(
        f"Steam temperature   : "
        f"{recommended['steam_temperature']:.2f} °F"
    )

    print(
        f"Injection pressure  : "
        f"{recommended['injection_pressure']:.2f}"
    )

    print(
        f"Injection duration  : "
        f"{recommended['injection_duration']:.2f} hr"
    )

    print(
        f"Soak time            : "
        f"{recommended['soak_time']:.2f} hr"
    )

    print(
        f"Steam volume         : "
        f"{recommended['steam_volume']:.2f}"
    )

    print(
        f"Stroke length        : "
        f"{recommended['stroke_length']:.2f}"
    )

    print(
        f"SPM                  : "
        f"{recommended['spm']:.2f}"
    )

    print(
        f"VFD frequency        : "
        f"{recommended['vfd_frequency']:.2f} Hz"
    )

    print()

    print("=" * 70)
    print("PREDICTED OUTCOME")
    print("=" * 70)

    print(
        f"Temperature         : "
        f"{recommended['pred_temperature']:.2f} °C"
    )

    print(
        f"Oil rate            : "
        f"{recommended['pred_oil']:.2f} BOPD"
    )

    print(
        f"Rod floating risk   : "
        f"{recommended['rod_risk']:.2f}%"
    )

    print(
        f"Energy              : "
        f"{recommended['energy']:.2f}"
    )

    print(
        f"SOR proxy           : "
        f"{recommended['sor_proxy']:.2f}"
    )

    print()

    print("=" * 70)
    print("CHANGES VS BASELINE")
    print("=" * 70)

    print(
        f"Oil change           : "
        f"{recommended['oil_change_pct']:.2f}%"
    )

    print(
        f"Risk change          : "
        f"{recommended['risk_change_pct']:.2f}%"
    )

    print(
        f"Energy change        : "
        f"{recommended['energy_change_pct']:.2f}%"
    )

    print(
        f"Optimization score   : "
        f"{recommended['optimization_score']:.4f}"
    )

    print()

    print("Optimizer test completed successfully.")
