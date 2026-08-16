from pathlib import Path

import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry


def create_client(cache_dir: str | Path):

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_session = requests_cache.CachedSession(
        str(cache_dir),
        expire_after=-1,
    )

    retry_session = retry(
        cache_session,
        retries=5,
        backoff_factor=0.2,
    )

    return openmeteo_requests.Client(
        session=retry_session
    )


def download_hourly_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    cache_dir: str | Path,
) -> pd.DataFrame:

    client = create_client(cache_dir)

    url = (
        "https://archive-api.open-meteo.com/v1/archive"
    )

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,

        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "shortwave_radiation",
        ],

        "timezone": "Asia/Tehran",

        "temperature_unit": "celsius",

        "cell_selection": "land",
    }

    responses = client.weather_api(
        url,
        params=params,
    )

    response = responses[0]

    hourly = response.Hourly()

    # ---------------------------------------------------------
    # Open-Meteo hourly timestamps
    # ---------------------------------------------------------

    timestamps = pd.date_range(
        start=pd.to_datetime(
            hourly.Time(),
            unit="s",
        ),
        end=pd.to_datetime(
            hourly.TimeEnd(),
            unit="s",
        ),
        freq=pd.Timedelta(
            seconds=hourly.Interval()
        ),
        inclusive="left",
    )

    # ---------------------------------------------------------
    # Normalize to exact hourly timestamps
    #
    # Open-Meteo may return :30 timestamps depending on
    # timezone / API configuration. For our application,
    # the feeder data represent hourly intervals beginning
    # at HH:00.
    # ---------------------------------------------------------

    timestamps = (
        timestamps
        .floor("h")
    )

    weather = pd.DataFrame(
        {
            "Timestamp": timestamps,
            "Temperature": (
                hourly.Variables(0)
                .ValuesAsNumpy()
            ),
            "RelativeHumidity": (
                hourly.Variables(1)
                .ValuesAsNumpy()
            ),
            "SolarRadiation": (
                hourly.Variables(2)
                .ValuesAsNumpy()
            ),
        }
    )

    # ---------------------------------------------------------
    # Check duplicate timestamps
    # ---------------------------------------------------------

    if weather["Timestamp"].duplicated().any():

        duplicates = weather[
            weather["Timestamp"].duplicated(
                keep=False
            )
        ]

        raise ValueError(
            "Duplicate weather timestamps detected:\n"
            f"{duplicates.head(20)}"
        )

    return weather