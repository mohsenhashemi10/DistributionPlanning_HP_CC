import numpy as np
import pandas as pd


def calculate_monthly_temperature(
    weather,
    timestamps,
):

    weather = weather.copy()

    weather["Timestamp"] = pd.to_datetime(
        weather["Timestamp"]
    )

    weather["JalaliDate"] = None

    # Merge only by Gregorian timestamp
    result = timestamps.merge(
        weather[
            [
                "Timestamp",
                "Temperature",
            ]
        ],
        on="Timestamp",
        how="left",
    )

    result["Month"] = (
        result["Timestamp"]
        .dt.month
    )

    return (
        result
        .groupby("Month")
        .agg(
            MeanTemperature=(
                "Temperature",
                "mean"
            )
        )
        .reset_index()
    )

import numpy as np
import pandas as pd


def estimate_thermal_gas(
    gas_monthly,
    weather_monthly,
    base_temperature=18.0,
    min_valid_year=1397,
    baseline_quantile=0.10,
):
    """
    Estimate temperature-dependent gas consumption.

    The original output column names are preserved for
    compatibility with the rest of the project.

    Parameters
    ----------
    gas_monthly : pd.DataFrame
        Monthly gas consumption with:
        JalaliYear, JalaliMonth, Gas_m3

    weather_monthly : pd.DataFrame
        Monthly weather data with:
        JalaliYear, JalaliMonth, MeanTemperature

    base_temperature : float
        Heating degree-day base temperature (°C).

    min_valid_year : int
        First Jalali year considered reliable.

    baseline_quantile : float
        Quantile used to estimate the non-temperature-
        dependent gas baseline.
    """

    gas = gas_monthly.copy()

    weather = weather_monthly.copy()

    # --------------------------------------------------
    # Remove unreliable early gas data
    # --------------------------------------------------

    gas = gas[
        gas["JalaliYear"] >= min_valid_year
    ].copy()

    if gas.empty:
        raise ValueError(
            "No gas data remain after applying "
            f"min_valid_year={min_valid_year}."
        )

    # --------------------------------------------------
    # Merge temperature
    # --------------------------------------------------

    df = gas.merge(
        weather,
        on=[
            "JalaliYear",
            "JalaliMonth",
        ],
        how="left",
    )

    # --------------------------------------------------
    # Validate temperature
    # --------------------------------------------------

    if df["MeanTemperature"].isna().any():

        missing = df.loc[
            df["MeanTemperature"].isna(),
            [
                "JalaliYear",
                "JalaliMonth",
            ],
        ]

        raise ValueError(
            "Missing monthly temperature values:\n"
            f"{missing}"
        )

    # --------------------------------------------------
    # Heating Degree Days
    # --------------------------------------------------

    df["HDD"] = np.maximum(
        base_temperature
        - df["MeanTemperature"],
        0,
    )

    # --------------------------------------------------
    # Estimate non-thermal gas baseline
    #
    # DO NOT use minimum gas consumption.
    #
    # Very small values may correspond to incomplete
    # metering or unreliable historical observations.
    # --------------------------------------------------

    valid_gas = df.loc[
        df["Gas_m3"] > 0,
        "Gas_m3",
    ]

    if valid_gas.empty:
        raise ValueError(
            "No positive gas consumption values "
            "are available."
        )

    gas_base = valid_gas.quantile(
        baseline_quantile
    )

    df["BaseGas_m3"] = gas_base

    # --------------------------------------------------
    # Temperature-dependent gas
    # --------------------------------------------------

    df["TemperatureDependentGas_m3"] = np.maximum(
        df["Gas_m3"]
        - gas_base,
        0,
    )

    # --------------------------------------------------
    # Useful thermal gas
    # --------------------------------------------------

    df["ThermalGas_m3"] = (
        df["TemperatureDependentGas_m3"]
    )

    return df


def convert_gas_to_thermal_energy(
    df,
    gas_energy_kwh_per_m3=10.0,
    thermal_efficiency=0.85,
):
    """
    Convert thermal gas consumption to useful thermal energy.

    Existing output column names are preserved.
    """

    result = df.copy()

    result["GasEnergy_kWh"] = (
        result["ThermalGas_m3"]
        * gas_energy_kwh_per_m3
    )

    result["ThermalEnergy_kWh"] = (
        result["GasEnergy_kWh"]
        * thermal_efficiency
    )

    return result



