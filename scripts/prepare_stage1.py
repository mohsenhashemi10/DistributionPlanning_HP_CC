import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from thermal_dnep.config.loader import load_config
from thermal_dnep.data.preprocessing import (
    preprocess_feeder_data,
)

from thermal_dnep.data.validation import (
    generate_quality_report,
    print_diagnostic_report,
)


def main():

    print("=" * 70)
    print("THERMAL DNEP - STAGE 1 DATA PREPARATION")
    print("=" * 70)

    config = load_config()

    station_code = config["feeder"]["station_code"]

    raw_file = (
        PROJECT_ROOT
        / config["paths"]["raw_data"]
        / "feeder"
        / f"{station_code}.csv"
    )

    output_dir = (
        PROJECT_ROOT
        / config["paths"]["processed_data"]
        / "stage1"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        output_dir
        / f"{station_code}_stage1_base.parquet"
    )

    print(f"\nReading:")
    print(raw_file)

    if not raw_file.exists():
        raise FileNotFoundError(
            f"Raw feeder file not found:\n{raw_file}"
        )

    df_raw = pd.read_csv(
        raw_file,
        encoding="utf-8-sig",
    )

    print(f"Raw rows: {len(df_raw):,}")

    print("\nConverting wide format to long format...")

    df = preprocess_feeder_data(df_raw)

    print(f"Long rows: {len(df):,}")

    print("\nRunning data quality checks...")

    report = generate_quality_report(
        raw_df=df_raw,
        long_df=df,
    )

    print("\n" + "-" * 70)
    print("DATA QUALITY REPORT")
    print("-" * 70)

    for key, value in report.items():
        print(f"{key}: {value:,}")

    print_diagnostic_report(
        raw_df=df_raw,
        long_df=df,
    )

    print("\nDate and hour sample:")
    print(
        df[
            [
                "Date",
                "JalaliDate",
                "Hour",
                "JalaliHour",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    print("\nFeeder count:")
    print(
        df["ToolPGDSCode"].nunique()
    )

    print("\nSaving processed dataset...")

    df.to_parquet(
        output_file,
        index=False,
    )

    print(f"\nSaved to:")
    print(output_file)

    print("\nDone.")


if __name__ == "__main__":
    main()