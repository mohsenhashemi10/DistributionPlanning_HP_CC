from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from thermal_dnep.network.ieee33 import create_ieee33_network
from thermal_dnep.dnep.solve import build_and_solve
from thermal_dnep.dnep.results import extract_results
from thermal_dnep.dnep.visualization_standard import show_results_standard
from thermal_dnep.dnep.technology_model import TechnologyParams
from thermal_dnep.dnep.export_variables import (
    save_all_variables,
    print_variable_summary,
)

FEEDER_CODE = "TAZB6T01"

LOAD_FILE = (
    PROJECT_ROOT
    / "data/processed/stage5/network"
    / f"{FEEDER_CODE}_ieee33_hourly_loads.parquet"
)

OUTPUT_DIR = PROJECT_ROOT / "data/processed/stage6/dnep"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ELECTRIFICATION_LEVEL = 0.30
SOLVER_NAME = "appsi_highs"


def main():
    print("=" * 70)
    print("STAGE 6 - STANDARD IEEE 33 VISUALIZATION")
    print("=" * 70)

    if not LOAD_FILE.exists():
        raise FileNotFoundError(f"فایل بار یافت نشد: {LOAD_FILE}")

    tech = TechnologyParams()

    print(f"\nSolving model at {ELECTRIFICATION_LEVEL:.0%} electrification...")
    m, res = build_and_solve(
        parquet_path=str(LOAD_FILE),
        electrification_level=ELECTRIFICATION_LEVEL,
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
    results = extract_results(m, tech=tech)

    print(f"\nTotal cost (NPV): {results['total_cost_npv']:,.0f}")
    print(f"Lines new: {len(results['lines_new'])}")
    print(f"Lines reinforced: {len(results['lines_reinforced'])}")
    print(f"Substations upgraded: {len(results['substations_upgraded'])}")

    net = create_ieee33_network()

    output_html = OUTPUT_DIR / f"{FEEDER_CODE}_network_standard.html"

    show_results_standard(
        net,
        results,
        electrification_level=ELECTRIFICATION_LEVEL,
        output_html=str(output_html),
    )

    print("\nVisualization completed.")


if __name__ == "__main__":
    main()