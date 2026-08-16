from pathlib import Path
import sys

import pandas as pd


# ============================================================
# Project paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ============================================================
# Imports
# ============================================================

from thermal_dnep.utils.dates import (
    jalali_to_gregorian,
)

from thermal_dnep.weather.openmeteo import (
    download_hourly_weather,
)

from thermal_dnep.weather.enrichment import (
    enrich_feeder_with_weather,
    validate_weather_merge,
)


# ============================================================
# Configuration
# ============================================================

LATITUDE = 35.6996
LONGITUDE = 51.3675

STAGE1_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "stage1"
    / "tazb_stage1_base.parquet"
)

WEATHER_CACHE = (
    PROJECT_ROOT
    / "data"
    / "weather"
    / "cache"
)

WEATHER_FILE = (
    PROJECT_ROOT
    / "data"
    / "weather"
    / "tazb_weather_hourly.parquet"
)

STAGE2_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "stage2"
    / "tazb_feeder_weather.parquet"
)


# ============================================================
# Date range
# ============================================================

def get_date_range(df):

    dates = (
        df["JalaliDate"]
        .dropna()
        .apply(jalali_to_gregorian)
    )

    start_date = min(dates) - pd.Timedelta(days=1)
    end_date = max(dates) + pd.Timedelta(days=1)

    return (
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 70)
    print("STAGE 2 - WEATHER ENRICHMENT")
    print("=" * 70)

    # ---------------------------------------------------------
    # Load Stage 1
    # ---------------------------------------------------------

    print("\nLoading feeder data...")

    feeder = pd.read_parquet(
        STAGE1_FILE
    )

    print(
        f"Feeder rows: {len(feeder):,}"
    )

    # ---------------------------------------------------------
    # Determine date range
    # ---------------------------------------------------------

    start_date, end_date = (
        get_date_range(feeder)
    )

    print(
        f"Weather start: {start_date}"
    )

    print(
        f"Weather end  : {end_date}"
    )

    # ---------------------------------------------------------
    # Download weather
    # ---------------------------------------------------------

    print("\nDownloading weather...")

    weather = download_hourly_weather(
        latitude=LATITUDE,
        longitude=LONGITUDE,
        start_date=start_date,
        end_date=end_date,
        cache_dir=WEATHER_CACHE,
    )

    print(
        f"Weather rows: {len(weather):,}"
    )

    print("\nWeather sample:")
    print(
        weather.head().to_string(
            index=False
        )
    )

    # ---------------------------------------------------------
    # Save raw weather
    # ---------------------------------------------------------

    WEATHER_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    weather.to_parquet(
        WEATHER_FILE,
        index=False,
    )

    # ---------------------------------------------------------
    # Merge
    # ---------------------------------------------------------

    print("\nMerging feeder and weather...")

    result = enrich_feeder_with_weather(
        feeder,
        weather,
    )


    missing_weather = result[
        result["Temperature"].isna()
    ][
        [
            "Date",
            "ToolPGDSCode",
            "JalaliHour",
            "Timestamp",
        ]
    ]

    print("\nMissing weather records:")
    print(
        missing_weather.to_string(
            index=False
        )
    )

    print("\nMissing timestamp range:")
    print(
        missing_weather["Timestamp"]
        .drop_duplicates()
        .sort_values()
        .to_string(index=False)
    )

    # ---------------------------------------------------------
    # Validate
    # ---------------------------------------------------------

    report = validate_weather_merge(
        result
    )

    print("\nWeather merge report")
    print("-" * 70)

    for key, value in report.items():
        print(f"{key}: {value}")

    # ---------------------------------------------------------
    # Save Stage 2
    # ---------------------------------------------------------

    STAGE2_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_parquet(
        STAGE2_FILE,
        index=False,
    )

    print("\nSaved to:")
    print(STAGE2_FILE)

    print("\nStage 2 completed.")


if __name__ == "__main__":
    main()