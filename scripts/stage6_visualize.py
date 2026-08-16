from pathlib import Path
import sys
import json
from datetime import datetime

import pandas as pd


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

from thermal_dnep.dnep.solve import (
    build_and_solve,
)

from thermal_dnep.dnep.results import (
    extract_results,
)

from thermal_dnep.dnep.technology_model import (
    TechnologyParams,
)

# from thermal_dnep.dnep.visualization_igraph import (
#     show_results,
# )

from thermal_dnep.dnep.visualization import (
    show_results,
)

from thermal_dnep.dnep.export_variables import (
    save_all_variables,
    print_variable_summary,
)

# ============================================================
# CONFIG
# ============================================================

FEEDER_CODE = "TAZB6T01"

LOAD_FILE = (
    PROJECT_ROOT
    / "data/processed/stage5/network"
    / f"{FEEDER_CODE}_ieee33_hourly_loads.parquet"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data/processed/stage6/dnep"
)

INPUT_DIR = (
    OUTPUT_DIR
    / "inputs"
    / f"{FEEDER_CODE}_{int(0.30 * 100)}pct"
)

RESULT_DIR = (
    OUTPUT_DIR
    / "results"
    / f"{FEEDER_CODE}_{int(0.30 * 100)}pct"
)

FIGURE_DIR = (
    OUTPUT_DIR
    / "figures"
    / f"{FEEDER_CODE}_{int(0.30 * 100)}pct"
)

for directory in [
    OUTPUT_DIR,
    INPUT_DIR,
    RESULT_DIR,
    FIGURE_DIR,
]:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# SCENARIO
# ============================================================

ELECTRIFICATION_LEVEL = 0.30

SOLVER_NAME = "appsi_highs"


# ============================================================
# INPUT SNAPSHOT
# ============================================================

def save_input_snapshot(
    load_file,
    input_dir,
    technology_params,
):
    """
    Save an exact snapshot of the inputs used by
    the optimization run.
    """

    print("\nSaving model input snapshot...")

    # --------------------------------------------------------
    # 1. Load data
    # --------------------------------------------------------

    loads = pd.read_parquet(
        load_file
    )

    loads.to_parquet(
        input_dir / "bus_hourly_loads.parquet",
        index=False,
    )

    # --------------------------------------------------------
    # 2. Scenario
    # --------------------------------------------------------

    scenario = {
        "feeder_code": FEEDER_CODE,
        "electrification_level": (
            ELECTRIFICATION_LEVEL
        ),
        "solver": SOLVER_NAME,
        "load_file": str(load_file),
        "created_at": datetime.now().isoformat(),
    }

    with open(
        input_dir / "scenario.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            scenario,
            f,
            ensure_ascii=False,
            indent=4,
        )

    # --------------------------------------------------------
    # 3. Technology parameters
    # --------------------------------------------------------

    technology_data = {}

    for category in [
        "heating_technologies",
        "cooling_technologies",
    ]:

        technologies = getattr(
            technology_params,
            category,
            [],
        )

        technology_data[category] = []

        for technology in technologies:

            data = {}

            if hasattr(
                technology,
                "__dict__",
            ):

                for key, value in vars(
                    technology
                ).items():

                    if isinstance(
                        value,
                        (
                            str,
                            int,
                            float,
                            bool,
                            type(None),
                        ),
                    ):

                        data[key] = value

            else:

                data["name"] = str(
                    technology
                )

            technology_data[
                category
            ].append(data)

    with open(
        input_dir / "technology_parameters.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            technology_data,
            f,
            ensure_ascii=False,
            indent=4,
            default=str,
        )

    # --------------------------------------------------------
    # 4. Basic load statistics
    # --------------------------------------------------------

    numeric_columns = [
        column
        for column in loads.columns
        if pd.api.types.is_numeric_dtype(
            loads[column]
        )
    ]

    load_summary = (
        loads[numeric_columns]
        .describe()
        .T
        .reset_index()
        .rename(
            columns={
                "index": "Variable"
            }
        )
    )

    load_summary.to_csv(
        input_dir / "load_statistics.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"  Input snapshot: {input_dir}"
    )

    print(
        f"  Load rows    : {len(loads):,}"
    )


# ============================================================
# RESULT SNAPSHOT
# ============================================================

def save_results(
    results,
    result_dir,
):
    """
    Save optimization results.
    """

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = {
        "total_cost_npv": results.get(
            "total_cost_npv"
        ),
        "last_year": results.get(
            "last_year"
        ),
        "number_of_new_lines": len(
            results.get(
                "lines_new",
                [],
            )
        ),
        "number_of_reinforced_lines": len(
            results.get(
                "lines_reinforced",
                [],
            )
        ),
        "number_of_upgraded_substations": len(
            results.get(
                "substations_upgraded",
                [],
            )
        ),
        "number_of_pv_buses": len(
            results.get(
                "pv_capacity",
                {}
            )
        ),
        "number_of_dg_buses": len(
            results.get(
                "dg_capacity",
                {}
            )
        ),
    }

    with open(
        result_dir / "summary.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=4,
            default=str,
        )

    # --------------------------------------------------------
    # Timeline
    # --------------------------------------------------------

    if "timeline" in results:

        timeline = pd.DataFrame(
            results["timeline"]
        )

        timeline.to_csv(
            result_dir / "timeline.csv",
            index=False,
            encoding="utf-8-sig",
        )

    # --------------------------------------------------------
    # Lines
    # --------------------------------------------------------

    for name in [
        "lines_new",
        "lines_reinforced",
        "substations_upgraded",
    ]:

        values = results.get(
            name,
            [],
        )

        if values:

            pd.DataFrame(
                values
            ).to_csv(
                result_dir
                / f"{name}.csv",
                index=False,
                encoding="utf-8-sig",
            )

    # --------------------------------------------------------
    # PV
    # --------------------------------------------------------

    pv = results.get(
        "pv_capacity",
        {},
    )

    if pv:

        pd.DataFrame(
            [
                {
                    "Bus": bus,
                    "PV_MW": capacity,
                }
                for bus, capacity
                in pv.items()
            ]
        ).to_csv(
            result_dir / "pv_capacity.csv",
            index=False,
            encoding="utf-8-sig",
        )

    # --------------------------------------------------------
    # DG
    # --------------------------------------------------------

    dg = results.get(
        "dg_capacity",
        {},
    )

    if dg:

        pd.DataFrame(
            [
                {
                    "Bus": bus,
                    "DG_MW": capacity,
                }
                for bus, capacity
                in dg.items()
            ]
        ).to_csv(
            result_dir / "dg_capacity.csv",
            index=False,
            encoding="utf-8-sig",
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("STAGE 6 - DNEP VISUALIZATION")
    print("=" * 70)

    # --------------------------------------------------------
    # 1. Check input
    # --------------------------------------------------------

    if not LOAD_FILE.exists():

        raise FileNotFoundError(
            f"Load file not found:\n"
            f"{LOAD_FILE}"
        )

    # --------------------------------------------------------
    # 2. Technology parameters
    # --------------------------------------------------------

    tech = TechnologyParams()

    # --------------------------------------------------------
    # 3. Save exact input snapshot
    # --------------------------------------------------------

    save_input_snapshot(
        load_file=LOAD_FILE,
        input_dir=INPUT_DIR,
        technology_params=tech,
    )

    # --------------------------------------------------------
    # 4. Solve
    # --------------------------------------------------------

    print(
        f"\nSolving model at "
        f"{ELECTRIFICATION_LEVEL:.0%} "
        f"electrification..."
    )

    m, res = build_and_solve(
        parquet_path=str(
            LOAD_FILE
        ),
        electrification_level=(
            ELECTRIFICATION_LEVEL
        ),
        solver_name=SOLVER_NAME,
    )


    print_variable_summary(m)


    # ذخیره کامل در فایل
    VARS_DIR = OUTPUT_DIR / "variables"
    saved = save_all_variables(
        m,
        output_dir=VARS_DIR,
        prefix=f"{FEEDER_CODE}",
        fmt="csv",   # یا "parquet" برای حجم کمتر
    )

    # --------------------------------------------------------
    # 5. Extract results
    # --------------------------------------------------------

    results = extract_results(
        m,
        tech=tech,
    )

    # --------------------------------------------------------
    # 6. Print results
    # --------------------------------------------------------

    print(
        f"\nTotal cost (NPV): "
        f"{results['total_cost_npv']:,.0f}"
    )

    print(
        f"Lines new: "
        f"{len(results['lines_new'])}"
    )

    print(
        f"Lines reinforced: "
        f"{len(results['lines_reinforced'])}"
    )

    print(
        f"Substations upgraded: "
        f"{len(results['substations_upgraded'])}"
    )

    # --------------------------------------------------------
    # 7. Save results
    # --------------------------------------------------------

    save_results(
        results=results,
        result_dir=RESULT_DIR,
    )

    # --------------------------------------------------------
    # 8. Create network
    # --------------------------------------------------------

    net = create_ieee33_network()

    # --------------------------------------------------------
    # 9. Visualization
    # --------------------------------------------------------

    output_figure = OUTPUT_DIR / f"{FEEDER_CODE}_network_map.png"

    show_results(
        net,
        results,
        save_path=str(output_figure),
    )

    print(
        "\nVisualization completed."
    )

    print(
        "\nInput files:"
    )

    print(
        INPUT_DIR
    )

    print(
        "\nResult files:"
    )

    print(
        RESULT_DIR
    )

    print(
        "\nFigure:"
    )

    print(
        output_figure
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()