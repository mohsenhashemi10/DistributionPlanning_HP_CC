import numpy as np
import pandas as pd




def calculate_feeder_cooling_shares(
    cooling_df,
):
    df = cooling_df.copy()

    required = [
        "ToolPGDSCode",
        "CoolingLoad",
        "Timestamp",
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing cooling columns: {missing}"
        )

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"]
    )

    df["Month"] = (
        df["Timestamp"].dt.month
    )

    # --------------------------------------------------
    # 1. Total cooling energy per feeder (all months)
    # --------------------------------------------------
    feeder_total = (
        df.groupby(
            "ToolPGDSCode",
            as_index=False,
        )
        .agg(
            CoolingEnergy_kWh=(
                "CoolingLoad",
                "sum",
            )
        )
    )

    # --------------------------------------------------
    # 2. Grand total across all feeders and months
    # --------------------------------------------------
    grand_total = feeder_total["CoolingEnergy_kWh"].sum()

    # --------------------------------------------------
    # 3. Calculate annual share per feeder
    # --------------------------------------------------
    feeder_total["TotalCooling_kWh"] = grand_total

    feeder_total["CoolingShare"] = np.where(
        grand_total > 0,
        feeder_total["CoolingEnergy_kWh"] / grand_total,
        0.0,
    )

    # --------------------------------------------------
    # 4. Expand to monthly format (preserve output schema)
    # --------------------------------------------------
    # ایجاد تمام ترکیب‌های ممکن ماه × فیدر برای حفظ ساختار خروجی قبلی
    all_months = pd.DataFrame({"Month": range(1, 13)})
    all_feeders = feeder_total[["ToolPGDSCode"]].drop_duplicates()

    monthly = (
        all_months
        .merge(all_feeders, how="cross")
        .merge(
            feeder_total,
            on="ToolPGDSCode",
            how="left",
        )
    )

    # پر کردن مقادیر NaN (برای فیدرهایی که هیچ بار سرمایشی نداشته‌اند)
    monthly["CoolingEnergy_kWh"] = (
        monthly["CoolingEnergy_kWh"].fillna(0.0)
    )
    monthly["TotalCooling_kWh"] = (
        monthly["TotalCooling_kWh"].fillna(0.0)
    )
    monthly["CoolingShare"] = (
        monthly["CoolingShare"].fillna(0.0)
    )

    return monthly


def allocate_heating_to_feeders(
    thermal_df,
    cooling_shares,
):

    thermal = thermal_df.copy()

    shares = cooling_shares.copy()

    result = thermal.merge(
        shares,
        left_on="JalaliMonth",
        right_on="Month",
        how="inner",
    )

    result["AllocatedHeating_kWh"] = (
        result["ThermalEnergy_kWh"]
        * result["CoolingShare"]
    )

    result["AllocatedHeating_MWh"] = (
        result["AllocatedHeating_kWh"]
        / 1000
    )

    return result


def validate_feeder_allocation(
    allocated,
):

    validation = (
        allocated
        .groupby(
            [
                "JalaliYear",
                "JalaliMonth",
            ],
            as_index=False,
        )
        .agg(
            TotalAllocatedHeating_kWh=(
                "AllocatedHeating_kWh",
                "sum",
            ),
            OriginalThermalEnergy_kWh=(
                "ThermalEnergy_kWh",
                "first",
            ),
        )
    )

    validation["Difference_kWh"] = (
        validation[
            "TotalAllocatedHeating_kWh"
        ]
        -
        validation[
            "OriginalThermalEnergy_kWh"
        ]
    )

    validation["RelativeError"] = (
        validation["Difference_kWh"]
        /
        validation[
            "OriginalThermalEnergy_kWh"
        ].replace(0, np.nan)
    )

    return validation