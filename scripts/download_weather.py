from pathlib import Path
import sys

import pandas as pd


# ============================================================
# Project path
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from thermal_dnep.weather.openmeteo import (
    download_hourly_weather,
)


# ============================================================
# Configuration
# ============================================================

LATITUDE = 35.0
LONGITUDE = 51.0

# WEATHER_START = "2020-03-20"
# WEATHER_END = "2023-09-22"

CACHE_DIR = (
    PROJECT_ROOT
    / "data"
    / "weather"
    / "cache"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "weather"
    / "tazb_weather_hourly.parquet"
)


def get_weather_date_range():
    """
    Get the exact Gregorian date range required
    by the feeder dataset.
    """

    feeder_file = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "stage1"
        / "tazb_stage1_base.parquet"
    )

    df = pd.read_parquet(
        feeder_file,
        columns=["JalaliDate"],
    )

    from thermal_dnep.utils.dates import (
        jalali_to_gregorian,
    )

    gregorian_dates = df[
        "JalaliDate"
    ].apply(
        jalali_to_gregorian
    )

    start_date = min(
        gregorian_dates
    ).strftime("%Y-%m-%d")

    end_date = max(
        gregorian_dates
    ).strftime("%Y-%m-%d")

    return start_date, end_date



# ============================================================
# Main
# ============================================================

def main():

    WEATHER_START, WEATHER_END = (
        get_weather_date_range()
    )

    print(f"Start    : {WEATHER_START}")
    print(f"End      : {WEATHER_END}")

    print("=" * 70)
    print("TAZB WEATHER DOWNLOAD")
    print("=" * 70)

    print(f"Latitude : {LATITUDE}")
    print(f"Longitude: {LONGITUDE}")
    print(f"Start    : {WEATHER_START}")
    print(f"End      : {WEATHER_END}")

    weather = download_hourly_weather(
        latitude=LATITUDE,
        longitude=LONGITUDE,
        start_date=WEATHER_START,
        end_date=WEATHER_END,
        cache_dir=CACHE_DIR,
    )

    print("\nWeather data:")
    print(weather.head())

    print("\nShape:")
    print(weather.shape)

    print("\nMissing values:")
    print(weather.isna().sum())

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    weather.to_parquet(
        OUTPUT_FILE,
        index=False,
    )

    print("\nSaved to:")
    print(OUTPUT_FILE)

    print("\nDone.")


if __name__ == "__main__":
    main()