import time

from app.simulator import simulate_well_tick
from app.supabase_client import supabase


# ============================================================
# SETTINGS
# ============================================================

UPDATE_INTERVAL_SECONDS = 10


# ============================================================
# GET WELLS
# ============================================================

def get_well_ids():

    response = (
        supabase
        .table("wells")
        .select("well_id")
        .order("well_id")
        .execute()
    )

    return [
        row["well_id"]
        for row in response.data
    ]


# ============================================================
# RUN ONE SIMULATION CYCLE
# ============================================================

def run_simulation_cycle(well_ids):

    success = 0
    failed = 0

    print("\n" + "=" * 70)
    print("WELLWISE — SIMULATED LIVE TELEMETRY CYCLE")
    print("=" * 70)

    for well_id in well_ids:

        try:

            result = simulate_well_tick(
                well_id
            )

            success += 1

            print(
                f"{well_id} | "
                f"{result['timestamp']} | "
                f"Temp: {result['reservoir_temperature']:.2f} °C | "
                f"Oil: {result['current_oil_rate']:.2f} BOPD | "
                f"SPM: {result['spm']:.2f} | "
                f"VFD: {result['vfd_frequency']:.2f} Hz"
            )

        except Exception as error:

            failed += 1

            print(
                f"{well_id} | ERROR | {error}"
            )

    print("-" * 70)
    print(
        f"Cycle complete | "
        f"Success: {success} | "
        f"Failed: {failed}"
    )


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    print("\n" + "=" * 70)
    print("WELLWISE — SIMULATED LIVE TELEMETRY ENGINE")
    print("=" * 70)

    print(
        f"\nUpdate interval: "
        f"{UPDATE_INTERVAL_SECONDS} seconds"
    )

    print(
        "Virtual time step per update: "
        "10 minutes"
    )

    print(
        "\nPress CTRL+C to stop the simulator."
    )

    # --------------------------------------------------------
    # Load wells once
    # --------------------------------------------------------

    try:

        well_ids = get_well_ids()

    except Exception as error:

        print(
            f"\n❌ Failed to load wells: {error}"
        )

        return

    if not well_ids:

        print(
            "\n❌ No wells found in Supabase."
        )

        return

    print(
        f"\n✅ Loaded {len(well_ids)} wells"
    )

    # --------------------------------------------------------
    # Continuous simulation
    # --------------------------------------------------------

    try:

        while True:

            run_simulation_cycle(
                well_ids
            )

            print(
                f"\nNext cycle in "
                f"{UPDATE_INTERVAL_SECONDS} seconds..."
            )

            time.sleep(
                UPDATE_INTERVAL_SECONDS
            )

    except KeyboardInterrupt:

        print(
            "\n\n🛑 WellWise simulator stopped."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
