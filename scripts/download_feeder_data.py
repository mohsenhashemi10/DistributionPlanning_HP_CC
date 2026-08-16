import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from thermal_dnep.config.loader import load_config
from thermal_dnep.data.feeder_loader import (
    load_feeder_data,
    save_raw_feeder_data,
)


def main():

    print("=" * 70)
    print("THERMAL DNEP - FEEDER DATA DOWNLOAD")
    print("=" * 70)

    config = load_config()

    station_code = config["feeder"]["station_code"]

    print(f"Station code: {station_code}")
    print("Connecting to SQL Server...")

    df = load_feeder_data(
        config=config,
        station_code=station_code
    )

    print(f"Rows retrieved: {len(df):,}")

    if df.empty:
        raise RuntimeError(
            f"No data returned for station: {station_code}"
        )

    print("\nColumns:")
    print(df.columns.tolist())

    print("\nDate range:")
    print(df["Date"].min(), "->", df["Date"].max())

    print("\nNumber of feeders:")
    print(df["ToolPGDSCode"].nunique())

    output_file = save_raw_feeder_data(
        df=df,
        config=config,
        station_code=station_code
    )

    print(f"\nRaw data saved to:")
    print(output_file)

    print("\nDone.")


if __name__ == "__main__":
    main()