from datetime import timedelta

import numpy as np
import pandas as pd

from app.supabase_client import supabase


# ============================================================
# SIMULATOR SETTINGS
# ============================================================

# Each simulator tick advances the virtual well time by 10 minutes.
VIRTUAL_STEP_MINUTES = 10


# ============================================================
# HELPER
# ============================================================

def clip(value, minimum, maximum):
    return float(np.clip(value, minimum, maximum))


# ============================================================
# SIMULATE ONE WELL
# ============================================================

def simulate_well_tick(well_id: str):
    """
    Generate one new controlled telemetry point for a well.

    This is simulated telemetry for the WellWise prototype.
    It is NOT real sensor data.
    """

    # --------------------------------------------------------
    # 1. Get latest telemetry
    # --------------------------------------------------------

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
        raise ValueError(
            f"No telemetry found for {well_id}"
        )

    current = response.data[0]

    # --------------------------------------------------------
    # 2. Convert values
    # --------------------------------------------------------

    temperature = float(
        current["reservoir_temperature"]
    )

    pressure = float(
        current["reservoir_pressure"]
    )

    viscosity = float(
        current["oil_viscosity"]
    )

    steam_rate = float(
        current["steam_rate"]
    )

    steam_volume = float(
        current["steam_volume"]
    )

    steam_temperature = float(
        current["steam_temperature"]
    )

    injection_pressure = float(
        current["injection_pressure"]
    )

    spm = float(
        current["spm"]
    )

    stroke_length = float(
        current["stroke_length"]
    )

    vfd_frequency = float(
        current["vfd_frequency"]
    )

    rod_load = float(
        current["rod_load"]
    )

    pump_load = float(
        current["pump_load"]
    )

    pump_fillage = float(
        current["pump_fillage"]
    )

    oil_rate = float(
        current["current_oil_rate"]
    )

    water_rate = float(
        current["current_water_rate"]
    )

    energy = float(
        current["current_energy"]
    )

    fluid_level = float(
        current["fluid_level"]
    )

    # --------------------------------------------------------
    # 3. Virtual time
    # --------------------------------------------------------

    current_time = pd.Timestamp(
        current["timestamp"]
    )

    next_time = (
        current_time
        + timedelta(minutes=VIRTUAL_STEP_MINUTES)
    )

    # --------------------------------------------------------
    # 4. Controlled changes
    # --------------------------------------------------------

    #
    # Small cyclical operating variation.
    # These changes are intentionally bounded.
    #

    phase = current.get("cycle_phase")

    if phase == "INJECTION":

        temperature_change = 0.08
        pressure_change = 0.03
        steam_rate_change = 0.03

    elif phase == "SOAK":

        temperature_change = 0.04
        pressure_change = -0.02
        steam_rate_change = -0.02

    elif phase == "RECOVERY":

        temperature_change = 0.01
        pressure_change = -0.03
        steam_rate_change = -0.04

    else:
        # PRODUCTION / unknown
        temperature_change = -0.015
        pressure_change = -0.02
        steam_rate_change = -0.01


    # --------------------------------------------------------
    # 5. Reservoir temperature
    # --------------------------------------------------------

    temperature = clip(
        temperature + temperature_change,
        35.0,
        120.0,
    )


    # --------------------------------------------------------
    # 6. Reservoir pressure
    # --------------------------------------------------------

    pressure = clip(
        pressure + pressure_change,
        10.0,
        80.0,
    )


    # --------------------------------------------------------
    # 7. Steam rate
    # --------------------------------------------------------

    steam_rate = clip(
        steam_rate + steam_rate_change,
        0.0,
        6.0,
    )


    # Steam volume follows steam rate.
    # 10-minute virtual interval = 1/6 hour.
    steam_volume = clip(
        steam_rate * (VIRTUAL_STEP_MINUTES / 60.0),
        0.0,
        1000.0,
    )


    # --------------------------------------------------------
    # 8. Viscosity
    # --------------------------------------------------------

    # Higher temperature → lower heavy-oil viscosity.
    viscosity_effect = (
        (temperature - float(current["reservoir_temperature"]))
        * 45.0
    )

    viscosity = clip(
        viscosity - viscosity_effect,
        2500.0,
        14000.0,
    )


    # --------------------------------------------------------
    # 9. Mechanical parameters
    # --------------------------------------------------------

    #
    # Small controlled SPM drift.
    #

    spm = clip(
        spm + np.random.normal(0, 0.02),
        1.0,
        3.0,
    )

    #
    # VFD tracks pump speed.
    #

    target_vfd = (
        20.0
        + (spm / 3.0) * 40.0
    )

    vfd_frequency = clip(
        0.85 * vfd_frequency
        + 0.15 * target_vfd
        + np.random.normal(0, 0.15),
        20.0,
        60.0,
    )


    # --------------------------------------------------------
    # 10. Rod load
    # --------------------------------------------------------

    viscosity_factor = np.log1p(
        viscosity / 5000.0
    )

    rod_load = clip(
        5.0
        + 3.0 * (spm / 3.2)
        + 2.0 * viscosity_factor,
        3.0,
        20.0,
    )


    # --------------------------------------------------------
    # 11. Pump load
    # --------------------------------------------------------

    pump_load = clip(
        32.0
        + 28.0 * (spm / 3.2)
        + 8.0 * (viscosity / 13000.0),
        30.0,
        95.0,
    )


    # --------------------------------------------------------
    # 12. Pump fillage
    # --------------------------------------------------------

    pump_fillage = clip(
        96.0
        - 18.0 * (spm / 3.2) ** 1.7
        - 14.0 * (viscosity / 13000.0)
        + 7.0 * (pressure / 50.0),
        25.0,
        100.0,
    )


    # --------------------------------------------------------
    # 13. Oil production
    # --------------------------------------------------------

    temperature_delta = (
        temperature
        - float(current["reservoir_temperature"])
    )

    viscosity_delta = (
        viscosity
        - float(current["oil_viscosity"])
    )

    production_change = (
        temperature_delta * 0.20
        - viscosity_delta * 0.0007
        + (pump_fillage - float(current["pump_fillage"])) * 0.03
        + np.random.normal(0, 0.08)
    )

    oil_rate = clip(
        oil_rate + production_change,
        30.0,
        150.0,
    )


    # --------------------------------------------------------
    # 14. Water rate
    # --------------------------------------------------------

    water_rate = clip(
        water_rate
        + np.random.normal(0, 0.10),
        5.0,
        60.0,
    )


    # --------------------------------------------------------
    # 15. Energy
    # --------------------------------------------------------

    pump_power_kw = (
        4.0
        + 18.0
        * (vfd_frequency / 60.0) ** 2
        * (0.55 + pump_load / 100.0)
    )

    energy = clip(
        pump_power_kw * 24.0,
        3.0 * 24.0,
        30.0 * 24.0,
    )


    # --------------------------------------------------------
    # 16. Fluid level
    # --------------------------------------------------------

    fluid_level = clip(
        fluid_level
        + (water_rate - oil_rate) * 0.002
        + np.random.normal(0, 0.10),
        5.0,
        100.0,
    )


    # --------------------------------------------------------
    # 17. Build new telemetry row
    # --------------------------------------------------------

    new_record = {
        "well_id": well_id,

        "timestamp": next_time.isoformat(),

        "css_cycle_id": current["css_cycle_id"],

        "cycle_day": current["cycle_day"],

        "cycle_phase": phase,

        "reservoir_pressure": pressure,

        "reservoir_temperature": temperature,

        "oil_viscosity": viscosity,

        "steam_rate": steam_rate,

        "steam_volume": steam_volume,

        "steam_temperature": steam_temperature,

        "injection_pressure": injection_pressure,

        "injection_duration": current["injection_duration"],

        "soak_time": current["soak_time"],

        "days_since_previous_css": (
            current["days_since_previous_css"]
        ),

        "stroke_length": stroke_length,

        "spm": spm,

        "vfd_frequency": vfd_frequency,

        "rod_load": rod_load,

        "pump_load": pump_load,

        "pump_fillage": pump_fillage,

        "current_oil_rate": oil_rate,

        "current_water_rate": water_rate,

        "current_energy": energy,

        "fluid_level": fluid_level,

        "source": "SIMULATED",
    }


    # --------------------------------------------------------
    # 18. Insert into Supabase
    # --------------------------------------------------------

    insert_response = (
        supabase
        .table("telemetry")
        .insert(new_record)
        .execute()
    )


    if not insert_response.data:
        raise RuntimeError(
            "Telemetry insert returned no data."
        )


    return insert_response.data[0]


# ============================================================
# TEST ONE TICK
# ============================================================

if __name__ == "__main__":

    WELL_ID = "BGW_01"

    print("\n" + "=" * 60)
    print("WELLWISE — SIMULATED TELEMETRY TEST")
    print("=" * 60)

    result = simulate_well_tick(
        WELL_ID
    )

    print("\n✅ New simulated telemetry created")

    print("\nWell:", result["well_id"])
    print("Timestamp:", result["timestamp"])

    print(
        f"Temperature: "
        f"{result['reservoir_temperature']:.2f} °C"
    )

    print(
        f"Pressure: "
        f"{result['reservoir_pressure']:.2f}"
    )

    print(
        f"Viscosity: "
        f"{result['oil_viscosity']:.2f} cP"
    )

    print(
        f"Oil rate: "
        f"{result['current_oil_rate']:.2f} BOPD"
    )

    print(
        f"SPM: "
        f"{result['spm']:.2f}"
    )

    print(
        f"VFD: "
        f"{result['vfd_frequency']:.2f} Hz"
    )

    print(
        f"Pump load: "
        f"{result['pump_load']:.2f}%"
    )

    print(
        f"Pump fillage: "
        f"{result['pump_fillage']:.2f}%"
    )

    print(
        f"Energy: "
        f"{result['current_energy']:.2f} kWh/day"
    )

    print(
        f"Source: "
        f"{result['source']}"
    )

    print("\n" + "=" * 60)
