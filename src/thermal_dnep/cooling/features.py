import pandas as pd
import numpy as np


def create_cooling_features(
    df: pd.DataFrame,
) -> pd.DataFrame:

    result = df.copy()

    result["Hour"] = (
        result["JalaliHour"]
        .astype(str)
        .str.extract(r"(\d+)")
        [0]
        .astype(int)
    )

    # ---------------------------------------------------------
    # Calendar features
    # ---------------------------------------------------------

    result["HourSin"] = np.sin(
        2 * np.pi * result["Hour"] / 24
    )

    result["HourCos"] = np.cos(
        2 * np.pi * result["Hour"] / 24
    )

    # ---------------------------------------------------------
    # Temperature features
    # ---------------------------------------------------------

    result["TemperatureSquared"] = (
        result["Temperature"] ** 2
    )

    # Cooling degree feature.
    # We intentionally use a fixed engineering threshold
    # rather than estimating a separate threshold for each
    # feeder.
    result["CDD"] = np.maximum(
        result["Temperature"] - 18.0,
        0,
    )

    result["CDDSquared"] = (
        result["CDD"] ** 2
    )

    # ---------------------------------------------------------
    # Humidity
    # ---------------------------------------------------------

    result["HumiditySquared"] = (
        result["RelativeHumidity"] ** 2
    )

    # ---------------------------------------------------------
    # Solar radiation
    # ---------------------------------------------------------

    result["SolarLog"] = np.log1p(
        np.maximum(
            result["SolarRadiation"],
            0,
        )
    )

    return result