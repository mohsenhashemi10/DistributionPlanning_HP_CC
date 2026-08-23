import re

import pandas as pd


HOUR_COLUMNS = [f"H{i:02d}" for i in range(1, 25)]

ID_COLUMNS = [
    "Date",
    "OperatorName",
    "StationPGDSCode",
    "Voltage",
    "ToolPGDSCode",
]

DAILY_KEYS = [
    "Date",
    "StationPGDSCode",
    "ToolPGDSCode",
]

def validate_input_columns(df: pd.DataFrame) -> None:
    """
    Validate that the raw feeder dataframe contains
    all required columns.
    """

    required_columns = ID_COLUMNS + HOUR_COLUMNS + ["Total"]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "The following required columns are missing:\n"
            f"{missing_columns}"
        )



def calculate_row_precision(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Calculate the total number of decimal digits
    across numeric hourly values and Total.

    Higher value means higher numerical precision.
    """

    numeric_columns = HOUR_COLUMNS + ["Total"]

    precision = pd.Series(
        0,
        index=df.index,
        dtype="int64",
    )

    for column in numeric_columns:

        values = (
            df[column]
            .astype(str)
            .str.strip()
        )

        decimal_digits = (
            values
            .str.split(".", n=1)
            .str[1]
            .fillna("")
            .str.len()
        )

        precision += decimal_digits.astype(int)

    return precision



def resolve_duplicate_daily_records(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resolve duplicate daily feeder records by retaining
    the record with the highest numerical precision.

    Duplicate definition:
        Date + StationPGDSCode + ToolPGDSCode
    """

    result = df.copy()

    result["_precision"] = calculate_row_precision(
        result
    )

    sort_columns = DAILY_KEYS + ["_precision"]

    result = (
        result
        .sort_values(
            sort_columns,
            ascending=[True, True, True, False],
        )
        .drop_duplicates(
            subset=DAILY_KEYS,
            keep="first",
        )
        .drop(
            columns="_precision"
        )
        .reset_index(drop=True)
    )

    return result



def wide_to_long(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert feeder hourly energy data from wide format
    (H01 ... H24) to long format.

    Returns
    -------
    pandas.DataFrame
        Columns include Date, feeder information,
        Hour and Load.
    """

    validate_input_columns(df)

    result = df.melt(
        id_vars=ID_COLUMNS + ["Total"],
        value_vars=HOUR_COLUMNS,
        var_name="Hour",
        value_name="Load",
    )

    result["Hour"] = (
        result["Hour"]
        .str.extract(r"(\d+)", expand=False)
        .astype(int)
    )

    return result


def convert_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert hourly load and Total to numeric values.
    """

    result = df.copy()

    result["Load"] = pd.to_numeric(
        result["Load"],
        errors="coerce"
    )

    result["Total"] = pd.to_numeric(
        result["Total"],
        errors="coerce"
    )

    return result


def normalize_jalali_date(date_series: pd.Series) -> pd.Series:
    """
    Normalize Jalali date values to YYYY/MM/DD strings.

    This function does not convert Jalali to Gregorian yet.
    """

    result = (
        date_series
        .astype(str)
        .str.strip()
        .str.replace("-", "/", regex=False)
        .str.replace(".", "/", regex=False)
    )

    return result


def combine_date_and_hour(
    date_series: pd.Series,
    hour_series: pd.Series,
) -> pd.Series:
    """
    Create a Jalali datetime string from date and hour.

    Hour 1 -> 01:00
    Hour 24 -> 24:00 representation is handled separately.
    """

    normalized_date = normalize_jalali_date(date_series)

    # Convert Hour 1..24 to 0..23 for datetime representation.
    hour_zero_based = hour_series.astype(int) - 1

    return (
        normalized_date
        + " "
        + hour_zero_based.astype(str).str.zfill(2)
        + ":00:00"
    )


def preprocess_feeder_data(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Main preprocessing pipeline for raw feeder data.
    """

    validate_input_columns(df)

    # ---------------------------------------------------------
    # 1. Resolve duplicate daily records
    # ---------------------------------------------------------

    df = resolve_duplicate_daily_records(df)

    # ---------------------------------------------------------
    # 2. Convert wide format to long format
    # ---------------------------------------------------------

    result = wide_to_long(df)

    # ---------------------------------------------------------
    # 3. Convert numeric columns
    # ---------------------------------------------------------

    result = convert_numeric_columns(result)

    # ---------------------------------------------------------
    # 4. Remove numerical noise around zero
    # ---------------------------------------------------------

    zero_threshold = 1e-3

    result.loc[
        result["Load"].abs() < zero_threshold,
        "Load"
    ] = 0.0

    # ---------------------------------------------------------
    # 5. Normalize Jalali date
    # ---------------------------------------------------------

    result["JalaliDate"] = normalize_jalali_date(
        result["Date"]
    )

    # ---------------------------------------------------------
    # 6. Create hour representation
    # ---------------------------------------------------------

    result["Hour"] = result["Hour"].astype(int)

    result["JalaliHour"] = (
        result["Hour"]
        .astype(str)
        .str.zfill(2)
    )

    return result