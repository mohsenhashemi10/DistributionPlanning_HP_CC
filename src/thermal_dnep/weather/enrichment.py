import pandas as pd

from thermal_dnep.utils.dates import (
    add_gregorian_timestamp,
)


def enrich_feeder_with_weather(
    feeder_df: pd.DataFrame,
    weather_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge feeder load data with weather data.

    Weather is shared among all feeders connected
    to the same substation.
    """

    feeder = feeder_df.copy()
    weather = weather_df.copy()

    # ---------------------------------------------------------
    # Create Gregorian timestamp
    # ---------------------------------------------------------

    feeder = add_gregorian_timestamp(
        feeder
    )

    # ---------------------------------------------------------
    # Normalize timestamps
    # ---------------------------------------------------------

    feeder["Timestamp"] = pd.to_datetime(
        feeder["Timestamp"]
    )

    weather["Timestamp"] = pd.to_datetime(
        weather["Timestamp"]
    )



    print("\nFeeder timestamp sample:")
    print(
        feeder["Timestamp"]
        .head()
        .to_string(index=False)
    )

    print("\nWeather timestamp sample:")
    print(
        weather["Timestamp"]
        .head()
        .to_string(index=False)
    )

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    if feeder["Timestamp"].dt.hour.nunique() == 1:
        raise ValueError(
            "Feeder Timestamp does not contain hourly "
            "variation. Check H01-H24 conversion."
        )

    if weather["Timestamp"].dt.minute.nunique() != 1:
        raise ValueError(
            "Weather timestamps have inconsistent minutes."
        )


    # ---------------------------------------------------------
    # Merge
    # ---------------------------------------------------------

    result = feeder.merge(
        weather,
        on="Timestamp",
        how="left",
        validate="many_to_one",
    )


    missing_weather = result[
        [
            "Temperature",
            "RelativeHumidity",
            "SolarRadiation",
        ]
    ].isna().sum()

    print("\nMissing weather values after merge:")
    print(missing_weather)

    return result


def validate_weather_merge(
    df: pd.DataFrame,
) -> dict:

    weather_columns = [
        "Temperature",
        "RelativeHumidity",
        "SolarRadiation",
    ]

    missing = (
        df[weather_columns]
        .isna()
        .sum()
    )

    return {
        "rows": len(df),
        "missing_temperature": int(
            missing["Temperature"]
        ),
        "missing_humidity": int(
            missing["RelativeHumidity"]
        ),
        "missing_solar": int(
            missing["SolarRadiation"]
        ),
        "timestamp_min": df["Timestamp"].min(),
        "timestamp_max": df["Timestamp"].max(),
    }