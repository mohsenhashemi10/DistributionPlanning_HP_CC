from pathlib import Path
import sys

import pandas as pd
import pandapower as pp


# ============================================================
# PROJECT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src")
)


# ============================================================
# IMPORTS
# ============================================================

from thermal_dnep.network.ieee33 import (
    create_ieee33_network,
)

from thermal_dnep.network.load_integration import (
    load_feeder_cooling,
    load_feeder_heating,
    create_hourly_heating_profile,
    build_integrated_load,
    allocate_feeder_load_to_buses,
    validate_bus_allocation,
)


# ============================================================
# CONFIG
# ============================================================

FEEDER_CODE = "TAZB6T01"

COOLING_FILE = (
    PROJECT_ROOT
    / "data/processed/stage3/cooling"
    / "tazb_cooling_estimation.parquet"
)

HEATING_FILE = (
    PROJECT_ROOT
    / "data/processed/stage4/thermal"
    / "TAZB_feeder_heating.parquet"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data/processed/stage5/network"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("STAGE 5 - FEEDER / IEEE-33 LOAD INTEGRATION")
    print("=" * 70)

    # --------------------------------------------------------
    # 1. IEEE-33
    # --------------------------------------------------------

    net = create_ieee33_network()

    print(
        f"\nIEEE-33 buses : {len(net.bus)}"
    )

    print(
        f"IEEE-33 loads : {len(net.load)}"
    )

    # --------------------------------------------------------
    # 2. Cooling
    # --------------------------------------------------------

    cooling = load_feeder_cooling(
        COOLING_FILE,
        FEEDER_CODE,
    )

    print(
        f"\nCooling rows : {len(cooling):,}"
    )

    # --------------------------------------------------------
    # 3. Heating
    # --------------------------------------------------------

    heating = load_feeder_heating(
        HEATING_FILE,
        FEEDER_CODE,
    )

    print(
        f"Heating rows : {len(heating):,}"
    )

    # --------------------------------------------------------
    # 4. HDD-based hourly heating
    # --------------------------------------------------------

    heating_profile = (
        create_hourly_heating_profile(
            cooling_df=cooling,
            heating_df=heating,
            base_temperature=18.0,
        )
    )

    # --------------------------------------------------------
    # 5. Integrated real feeder load
    # --------------------------------------------------------

    integrated = build_integrated_load(
        cooling,
        heating_profile,
    )

    print("\nIntegrated feeder load:")
    print(
        integrated[
            [
                "Timestamp",
                "BaseLoad_kWh",
                "CoolingLoad_kWh",
                "HeatingLoad_kWh",
                "IntegratedLoad_kWh",
            ]
        ].head()
    )

    # --------------------------------------------------------
    # 6. Allocate to IEEE-33 load points
    # --------------------------------------------------------

    allocated = (
        allocate_feeder_load_to_buses(
            net,
            integrated,
        )
    )

    print(
        "\nAllocated rows:",
        f"{len(allocated):,}",
    )

    # --------------------------------------------------------
    # 7. Validation
    # --------------------------------------------------------

    validation = (
        validate_bus_allocation(
            allocated
        )
    )

    print(
        "\nMaximum absolute allocation error:",
        validation["RelativeError"]
        .abs()
        .max(),
    )

    # --------------------------------------------------------
    # 8. Save
    # --------------------------------------------------------

    allocated_file = (
        OUTPUT_DIR
        / f"{FEEDER_CODE}_ieee33_hourly_loads.parquet"
    )

    validation_file = (
        OUTPUT_DIR
        / f"{FEEDER_CODE}_ieee33_allocation_validation.csv"
    )

    allocated.to_parquet(
        allocated_file,
        index=False,
    )

    validation.to_csv(
        validation_file,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # 9. Power-flow test for first hour
    # --------------------------------------------------------

    first_timestamp = (
        allocated["Timestamp"]
        .min()
    )

    first_hour = allocated[
        allocated["Timestamp"]
        == first_timestamp
    ]

    test_net = create_ieee33_network()

    test_net.load[
        "p_mw"
    ] = first_hour[
        "TotalLoadBus_MW"
    ].values

    pp.runpp(
        test_net,
        algorithm="bfsw",
    )

    print(
        "\nFirst-hour power flow:"
    )

    print(
        "Timestamp:",
        first_timestamp,
    )

    print(
        "Minimum voltage:",
        test_net.res_bus.vm_pu.min(),
    )

    print(
        "Maximum line loading:",
        test_net.res_line.loading_percent.max(),
    )

    print(
        "\nSaved:"
    )

    print(allocated_file)
    print(validation_file)

    print(
        "\nSTAGE 5 COMPLETED."
    )


if __name__ == "__main__":
    main()