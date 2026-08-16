from pathlib import Path
import sys

import pandas as pd


# ============================================================
# Project
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


# ============================================================
# Imports
# ============================================================

from thermal_dnep.cooling.features import (
    create_cooling_features,
)

from thermal_dnep.cooling.baseline import (
    estimate_baseline,
)

from thermal_dnep.cooling.model import (
    train_cooling_model,
)

from thermal_dnep.cooling.evaluation import (
    save_cooling_results,
    plot_cooling_example,
)


# ============================================================
# Paths
# ============================================================

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "stage2"
    / "tazb_feeder_weather.parquet"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "stage3"
    / "cooling"
)


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 70)
    print("STAGE 3 - COOLING LOAD ESTIMATION")
    print("=" * 70)

    # ---------------------------------------------------------
    # Load
    # ---------------------------------------------------------

    df = pd.read_parquet(
        INPUT_FILE
    )

    print(
        f"Input rows: {len(df):,}"
    )

    print(
        "Feeders:",
        df["ToolPGDSCode"]
        .nunique(),
    )

    # ---------------------------------------------------------
    # Features
    # ---------------------------------------------------------

    print(
        "\nCreating cooling features..."
    )

    df = create_cooling_features(
        df
    )

    # ---------------------------------------------------------
    # Baseline
    # ---------------------------------------------------------

    print(
        "Estimating electrical baseline..."
    )

    df = estimate_baseline(
        df
    )

    print(
        "\nCooling load statistics:"
    )

    print(
        df.groupby(
            "ToolPGDSCode"
        )[
            [
                "Load",
                "BaselineLoad",
                "CoolingLoad",
            ]
        ].mean()
    )

    # ---------------------------------------------------------
    # ML
    # ---------------------------------------------------------

    print(
        "\nTraining cooling models..."
    )

    (
        models,
        metrics,
        predictions,
    ) = train_cooling_model(
        df
    )

    # ---------------------------------------------------------
    # Results
    # ---------------------------------------------------------

    print(
        "\nModel performance:"
    )

    print(
        metrics.to_string(
            index=False
        )
    )

    save_cooling_results(
        metrics,
        predictions,
        OUTPUT_DIR,
    )

    plot_cooling_example(
        predictions,
        OUTPUT_DIR,
    )

    # ---------------------------------------------------------
    # Save complete dataset
    # ---------------------------------------------------------

    df.to_parquet(
        OUTPUT_DIR
        / "tazb_cooling_estimation.parquet",
        index=False,
    )

    print(
        "\nResults saved to:"
    )

    print(OUTPUT_DIR)

    print(
        "\nStage 3 completed."
    )


if __name__ == "__main__":
    main()