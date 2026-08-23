import pandas as pd


DAILY_KEYS = [
    "Date",
    "StationPGDSCode",
    "ToolPGDSCode",
]


def check_duplicate_daily_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return all duplicate daily feeder records.
    """

    duplicates = df[
        df.duplicated(
            subset=DAILY_KEYS,
            keep=False
        )
    ].copy()

    return duplicates


def check_missing_hourly_values(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Check missing hourly load values.
    """

    return df[df["Load"].isna()].copy()


def check_negative_loads(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Check negative hourly energy values.
    """

    return df[df["Load"] < 0].copy()


def check_daily_hour_count(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Check whether every feeder-day has exactly 24 hourly records.
    """

    counts = (
        df.groupby(DAILY_KEYS)["Hour"]
        .nunique()
        .reset_index(name="HourCount")
    )

    return counts[
        counts["HourCount"] != 24
    ].copy()


def check_total_consistency(
    df: pd.DataFrame,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """
    Compare SQL Total against the sum of H01...H24.

    Parameters
    ----------
    df : pandas.DataFrame
        Long-format feeder data.
    tolerance : float
        Relative tolerance.

    Returns
    -------
    pandas.DataFrame
        Daily records with inconsistent totals.
    """

    daily = (
        df.groupby(DAILY_KEYS)
        .agg(
            CalculatedTotal=("Load", "sum"),
            ReportedTotal=("Total", "first"),
        )
        .reset_index()
    )

    daily["Difference"] = (
        daily["CalculatedTotal"]
        - daily["ReportedTotal"]
    )

    denominator = daily["ReportedTotal"].abs()

    daily["RelativeDifference"] = (
        daily["Difference"].abs()
        / denominator.replace(0, pd.NA)
    )

    inconsistent = daily[
        daily["RelativeDifference"].fillna(0.0)
        > tolerance
    ].copy()

    return inconsistent


def generate_quality_report(
    raw_df: pd.DataFrame,
    long_df: pd.DataFrame,
) -> dict:

    duplicate_records = check_duplicate_daily_records(
        raw_df
    )

    missing_values = check_missing_hourly_values(
        long_df
    )

    negative_values = check_negative_loads(
        long_df
    )

    invalid_hours = check_daily_hour_count(
        long_df
    )

    total_inconsistencies = check_total_consistency(
        long_df
    )

    return {
        "raw_rows": len(raw_df),
        "long_rows": len(long_df),
        "number_of_feeders": long_df["ToolPGDSCode"].nunique(),
        "duplicate_daily_records": len(duplicate_records),
        "missing_load_values": len(missing_values),
        "negative_load_values": len(negative_values),
        "invalid_hour_counts": len(invalid_hours),
        "total_inconsistencies": len(total_inconsistencies),
    }


def print_diagnostic_report(
    raw_df: pd.DataFrame,
    long_df: pd.DataFrame,
) -> None:
    """
    Print detailed diagnostic information.
    """

    duplicates = check_duplicate_daily_records(
        raw_df
    )

    negatives = check_negative_loads(
        long_df
    )

    inconsistencies = check_total_consistency(
        long_df
    )

    print("\n")
    print("=" * 70)
    print("DETAILED DATA DIAGNOSTICS")
    print("=" * 70)

    # ---------------------------------------------------------
    # Duplicate records
    # ---------------------------------------------------------

    print("\n[1] DUPLICATE DAILY RECORDS")

    if duplicates.empty:
        print("No duplicate records found.")

    else:
        print(
            f"Duplicate rows: {len(duplicates):,}"
        )

        print("\nDuplicate daily groups:")

        duplicate_groups = (
            duplicates
            .groupby(DAILY_KEYS)
            .size()
            .reset_index(name="Count")
        )

        print(
            duplicate_groups.to_string(index=False)
        )

        print("\nSample duplicate records:")

        columns = [
            "Date",
            "StationPGDSCode",
            "ToolPGDSCode",
            "Total",
        ]

        print(
            duplicates[columns]
            .head(20)
            .to_string(index=False)
        )

    # ---------------------------------------------------------
    # Negative values
    # ---------------------------------------------------------

    print("\n[2] NEGATIVE HOURLY VALUES")

    if negatives.empty:
        print("No negative hourly values found.")

    else:
        print(
            f"Negative values: {len(negatives):,}"
        )

        print("\nNegative value samples:")

        columns = [
            "Date",
            "StationPGDSCode",
            "ToolPGDSCode",
            "Hour",
            "Load",
        ]

        print(
            negatives[columns]
            .head(30)
            .to_string(index=False)
        )

    # ---------------------------------------------------------
    # Total inconsistencies
    # ---------------------------------------------------------

    print("\n[3] TOTAL INCONSISTENCIES")

    if inconsistencies.empty:
        print("No Total inconsistencies found.")

    else:
        print(
            f"Inconsistent daily records: "
            f"{len(inconsistencies):,}"
        )

        columns = [
            "Date",
            "StationPGDSCode",
            "ToolPGDSCode",
            "CalculatedTotal",
            "ReportedTotal",
            "Difference",
            "RelativeDifference",
        ]

        print("\nSample inconsistencies:")

        print(
            inconsistencies[columns]
            .head(30)
            .to_string(index=False)
        )