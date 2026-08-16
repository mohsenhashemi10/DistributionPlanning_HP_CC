from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

DEFAULT_FEEDER = "TAZB6T01"


# ============================================================
# LOAD FEEDER DATA
# ============================================================

def load_feeder_cooling(
    file_path,
    feeder_code=DEFAULT_FEEDER,
):
    df = pd.read_parquet(file_path)

    df = df[
        df["ToolPGDSCode"].astype(str)
        == feeder_code
    ].copy()

    if df.empty:
        raise ValueError(
            f"No cooling data found for feeder "
            f"{feeder_code}"
        )

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"]
    )

    return df


# ============================================================
# LOAD HEATING DATA
# ============================================================

def load_feeder_heating(
    file_path,
    feeder_code=DEFAULT_FEEDER,
):
    df = pd.read_parquet(file_path)

    df = df[
        df["ToolPGDSCode"].astype(str)
        == feeder_code
    ].copy()

    if df.empty:
        raise ValueError(
            f"No heating data found for feeder "
            f"{feeder_code}"
        )

    return df


# ============================================================
# BUILD HOURLY HEATING PROFILE
# ============================================================

def create_hourly_heating_profile(
    cooling_df,
    heating_df,
    base_temperature=18.0,
):
    """
    Convert monthly allocated heating energy into
    an hourly heating profile using HDD.

    Heating is zero when:
        Temperature >= base_temperature

    For colder hours:
        Heating allocation is proportional to HDD.
    """

    df = cooling_df.copy()

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"]
    )

    # --------------------------------------------------------
    # Gregorian -> Jalali month is already available in
    # Stage 3 / feeder data.
    # --------------------------------------------------------

    if "JalaliDate" in df.columns:

        date_parts = (
            df["JalaliDate"]
            .astype(str)
            .str.replace("-", "/", regex=False)
            .str.split("/", expand=True)
        )

        df["JalaliYear"] = pd.to_numeric(
            date_parts[0],
            errors="coerce",
        )

        df["JalaliMonth"] = pd.to_numeric(
            date_parts[1],
            errors="coerce",
        )

    else:
        raise ValueError(
            "JalaliDate is required in cooling data."
        )

    # --------------------------------------------------------
    # HDD
    # --------------------------------------------------------

    df["HDD"] = np.maximum(
        base_temperature
        - df["Temperature"],
        0.0,
    )

    # --------------------------------------------------------
    # Monthly HDD sum
    # --------------------------------------------------------

    monthly_hdd = (
        df.groupby(
            [
                "JalaliYear",
                "JalaliMonth",
            ],
            as_index=False,
        )
        .agg(
            MonthlyHDD=("HDD", "sum")
        )
    )

    df = df.merge(
        monthly_hdd,
        on=[
            "JalaliYear",
            "JalaliMonth",
        ],
        how="left",
        validate="many_to_one",
    )

    # --------------------------------------------------------
    # Heating share of each hour
    # --------------------------------------------------------

    df["HeatingShare"] = np.where(
        df["MonthlyHDD"] > 0,
        df["HDD"] / df["MonthlyHDD"],
        0.0,
    )

    # --------------------------------------------------------
    # Monthly allocated heating
    # --------------------------------------------------------

    heating = heating_df[
        [
            "JalaliYear",
            "JalaliMonth",
            "AllocatedHeating_kWh",
        ]
    ].drop_duplicates(
        subset=[
            "JalaliYear",
            "JalaliMonth",
        ]
    )

    df = df.merge(
        heating,
        on=[
            "JalaliYear",
            "JalaliMonth",
        ],
        how="left",
    )

    df["AllocatedHeating_kWh"] = (
        df["AllocatedHeating_kWh"]
        .fillna(0.0)
    )

    # --------------------------------------------------------
    # Hourly heating energy
    # --------------------------------------------------------

    df["HeatingLoad_kWh"] = (
        df["AllocatedHeating_kWh"]
        * df["HeatingShare"]
    )

    return df


# ============================================================
# BUILD INTEGRATED HOURLY LOAD
# ============================================================

def build_integrated_load(
    cooling_df,
    heating_profile,
):
    """
    Create hourly feeder load consisting of:

        BaseLoad
        + CoolingLoad
        + HeatingLoad
    """

    df = cooling_df.copy()

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"]
    )

    heating = heating_profile[
        [
            "Timestamp",
            "HeatingLoad_kWh",
        ]
    ]

    df = df.merge(
        heating,
        on="Timestamp",
        how="left",
        validate="one_to_one",
    )

    df["HeatingLoad_kWh"] = (
        df["HeatingLoad_kWh"]
        .fillna(0.0)
    )

    # --------------------------------------------------------
    # Existing Stage 3 load
    # --------------------------------------------------------

    df["BaseLoad_kWh"] = (
        df["BaselineLoad"]*1000
    )

    df["CoolingLoad_kWh"] = (
        df["CoolingLoad"]*1000
    )

    # --------------------------------------------------------
    # Total thermal-aware load
    # --------------------------------------------------------

    df["IntegratedLoad_kWh"] = (
        df["BaseLoad_kWh"]
        + df["CoolingLoad_kWh"]
        + df["HeatingLoad_kWh"]
    )

    return df


# ============================================================
# VALIDATION
# ============================================================

def validate_heating_profile(
    df,
):
    """
    Verify that hourly heating sums back to
    monthly allocated heating.
    """

    result = (
        df.groupby(
            [
                "JalaliYear",
                "JalaliMonth",
            ],
            as_index=False,
        )
        .agg(
            HourlyHeating_kWh=(
                "HeatingLoad_kWh",
                "sum",
            ),
            AllocatedHeating_kWh=(
                "AllocatedHeating_kWh",
                "first",
            ),
        )
    )

    result["Difference_kWh"] = (
        result["HourlyHeating_kWh"]
        - result["AllocatedHeating_kWh"]
    )

    result["RelativeError"] = np.where(
        result["AllocatedHeating_kWh"] != 0,
        result["Difference_kWh"]
        / result["AllocatedHeating_kWh"],
        0.0,
    )

    return result

# ============================================================
# IEEE-33 LOAD-POINT ALLOCATION
# ============================================================

def get_ieee33_load_weights(net):
    """
    Calculate load-point weights from the original IEEE-33
    bus loads.

    Each existing IEEE-33 load keeps its relative share.
    """

    loads = net.load.copy()

    if loads.empty:
        raise ValueError(
            "IEEE-33 network contains no loads."
        )

    total_p = loads["p_mw"].sum()

    if total_p <= 0:
        raise ValueError(
            "Total IEEE-33 base load is zero."
        )

    weights = loads[
        ["bus", "p_mw"]
    ].copy()

    weights["LoadWeight"] = (
        weights["p_mw"] / total_p
    )

    return weights


def allocate_feeder_load_to_buses(
    net,
    integrated_load,
):
    """
    Allocate the actual feeder load to all IEEE-33
    load points according to their original load shares.

    The feeder hourly profile is preserved exactly.

    Columns produced:

        BaseLoad_MW
        CoolingLoad_MW
        HeatingLoad_MW
        TotalLoad_MW
    """

    df = integrated_load.copy()

    required = [
        "Timestamp",
        "BaseLoad_kWh",
        "CoolingLoad_kWh",
        "HeatingLoad_kWh",
        "IntegratedLoad_kWh",
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing integrated-load columns: {missing}"
        )

    weights = get_ieee33_load_weights(net)

    # --------------------------------------------------------
    # kWh -> average MW for hourly interval
    # --------------------------------------------------------

    df["BaseLoad_MW"] = (
        df["BaseLoad_kWh"] / 1000.0
    )

    df["CoolingLoad_MW"] = (
        df["CoolingLoad_kWh"] / 1000.0
    )

    df["HeatingLoad_MW"] = (
        df["HeatingLoad_kWh"] / 1000.0
    )

    df["TotalLoad_MW"] = (
        df["IntegratedLoad_kWh"] / 1000.0
    )

    # --------------------------------------------------------
    # Cartesian allocation:
    #
    # every hourly feeder profile
    # ×
    # every IEEE-33 load point
    # --------------------------------------------------------

    df["_key"] = 1
    weights["_key"] = 1

    result = df.merge(
        weights,
        on="_key",
        how="inner",
    )

    result.drop(
        columns=["_key"],
        inplace=True,
    )

    # --------------------------------------------------------
    # Allocate each component
    # --------------------------------------------------------

    result["BaseLoadBus_MW"] = (
        result["BaseLoad_MW"]
        * result["LoadWeight"]
    )

    result["CoolingLoadBus_MW"] = (
        result["CoolingLoad_MW"]
        * result["LoadWeight"]
    )

    result["HeatingLoadBus_MW"] = (
        result["HeatingLoad_MW"]
        * result["LoadWeight"]
    )

    result["TotalLoadBus_MW"] = (
        result["TotalLoad_MW"]
        * result["LoadWeight"]
    )

    return result


# ============================================================
# VALIDATE BUS ALLOCATION
# ============================================================

def validate_bus_allocation(
    allocated,
):
    """
    Verify that allocation across IEEE-33 buses preserves
    the original feeder load at every hour.
    """

    hourly = (
        allocated
        .groupby(
            "Timestamp",
            as_index=False,
        )
        .agg(
            FeederBase_MW=(
                "BaseLoad_MW",
                "first",
            ),
            AllocatedBase_MW=(
                "BaseLoadBus_MW",
                "sum",
            ),

            FeederCooling_MW=(
                "CoolingLoad_MW",
                "first",
            ),
            AllocatedCooling_MW=(
                "CoolingLoadBus_MW",
                "sum",
            ),

            FeederHeating_MW=(
                "HeatingLoad_MW",
                "first",
            ),
            AllocatedHeating_MW=(
                "HeatingLoadBus_MW",
                "sum",
            ),

            FeederTotal_MW=(
                "TotalLoad_MW",
                "first",
            ),
            AllocatedTotal_MW=(
                "TotalLoadBus_MW",
                "sum",
            ),
        )
    )

    hourly["TotalError_MW"] = (
        hourly["AllocatedTotal_MW"]
        - hourly["FeederTotal_MW"]
    )

    hourly["RelativeError"] = np.where(
        hourly["FeederTotal_MW"].abs() > 1e-12,
        hourly["TotalError_MW"]
        / hourly["FeederTotal_MW"],
        0.0,
    )

    return hourly