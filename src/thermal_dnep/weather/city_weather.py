from pathlib import Path

import pandas as pd

from thermal_dnep.weather.openmeteo import (
    download_hourly_weather,
)


def get_city_weather(
    latitude,
    longitude,
    start_date,
    end_date,
    weather_dir,
    cache_dir,
):

    weather_dir = Path(weather_dir)
    weather_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = (
        f"weather_"
        f"{latitude:.4f}_"
        f"{longitude:.4f}_"
        f"{start_date}_"
        f"{end_date}.parquet"
    )

    local_file = weather_dir / filename

    # --------------------------------------------------
    # Use existing data
    # --------------------------------------------------

    if local_file.exists():

        print(
            f"Using existing weather file: "
            f"{local_file.name}"
        )

        return pd.read_parquet(
            local_file
        )

    # --------------------------------------------------
    # Download
    # --------------------------------------------------

    print(
        "Weather file not found. "
        "Downloading from Open-Meteo..."
    )

    weather = download_hourly_weather(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        cache_dir=cache_dir,
    )

    weather.to_parquet(
        local_file,
        index=False
    )

    print(
        f"Weather saved: {local_file}"
    )

    return weather