import jdatetime
import pandas as pd



def gregorian_to_jalali_year_month(date_value):
    """
    Convert Gregorian date/datetime to Jalali year and month.
    """

    if pd.isna(date_value):
        return pd.NaT, pd.NaT

    timestamp = pd.Timestamp(date_value)

    jalali_date = jdatetime.date.fromgregorian(
        year=timestamp.year,
        month=timestamp.month,
        day=timestamp.day,
    )

    return (
        jalali_date.year,
        jalali_date.month,
    )

def jalali_to_gregorian(date_value):
    """
    Convert Jalali date string YYYY/MM/DD to Gregorian date.

    Parameters
    ----------
    date_value : str
        Jalali date such as 1401/01/01.

    Returns
    -------
    datetime.date
        Gregorian date.
    """

    if pd.isna(date_value):
        return pd.NaT

    date_value = str(date_value).strip()
    date_value = date_value.replace("-", "/")

    year, month, day = map(
        int,
        date_value.split("/")
    )

    return jdatetime.date(
        year,
        month,
        day
    ).togregorian()


def create_timestamp(
    jalali_date,
    hour,
):
    """
    Convert Jalali date + H01...H24 into a Gregorian
    timestamp representing the beginning of the hourly interval.

    Mapping:
        H01 -> 00:00
        H02 -> 01:00
        ...
        H24 -> 23:00
    """

    gregorian_date = jalali_to_gregorian(
        jalali_date
    )

    if pd.isna(gregorian_date):
        return pd.NaT

    hour = int(hour)

    if not 1 <= hour <= 24:
        raise ValueError(
            f"Hour must be between 1 and 24. Got: {hour}"
        )

    actual_hour = hour - 1

    return pd.Timestamp(
        year=gregorian_date.year,
        month=gregorian_date.month,
        day=gregorian_date.day,
        hour=actual_hour,
    )


import pandas as pd


def add_gregorian_timestamp(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add GregorianDate and hourly Timestamp.

    Hour convention:
        H01 -> 00:00
        H02 -> 01:00
        ...
        H24 -> 23:00
    """

    result = df.copy()

    # ---------------------------------------------------------
    # Convert Jalali date to Gregorian date
    # ---------------------------------------------------------

    result["GregorianDate"] = (
        result["JalaliDate"]
        .apply(jalali_to_gregorian)
    )

    result["GregorianDate"] = pd.to_datetime(
        result["GregorianDate"]
    )

    # ---------------------------------------------------------
    # Convert H01 ... H24 to hour offset
    # ---------------------------------------------------------

    hour_number = (
        result["JalaliHour"]
        .astype(str)
        .str.extract(r"(\d+)")
        [0]
        .astype(int)
    )

    # H01 = 00:00
    # H24 = 23:00
    result["HourOffset"] = (
        hour_number - 1
    )

    # ---------------------------------------------------------
    # Create exact hourly timestamp
    # ---------------------------------------------------------

    result["Timestamp"] = (
        result["GregorianDate"]
        + pd.to_timedelta(
            result["HourOffset"],
            unit="h",
        )
    )

    # ---------------------------------------------------------
    # Remove temporary column
    # ---------------------------------------------------------

    result.drop(
        columns=["HourOffset"],
        inplace=True,
    )

    return result