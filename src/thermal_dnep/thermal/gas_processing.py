import numpy as np
import pandas as pd

from thermal_dnep.thermal.city_matching import (
    normalize_text,
    find_column,
)




MONTH_MAP = {
    "فروردين": 1,
    "فروردین": 1,

    "ارديبهشت": 2,
    "اردیبهشت": 2,

    "خرداد": 3,

    "تير": 4,
    "تیر": 4,

    "مرداد": 5,

    "شهريور": 6,
    "شهریور": 6,

    "مهر": 7,
    "آبان": 8,
    "آذر": 9,

    "دي": 10,
    "دی": 10,

    "بهمن": 11,
    "اسفند": 12,
}


def load_gas_data(path):

    df = pd.read_excel(path)

    city_col = find_column(
        df,
        ["شهر"]
    )

    year_col = find_column(
        df,
        ["سال"]
    )

    if city_col is None or year_col is None:
        raise ValueError(
            "City/year columns not found."
        )

    df = df.rename(
        columns={
            city_col: "City",
            year_col: "JalaliYear",
        }
    )

    df["City"] = df["City"].apply(
        normalize_text
    )

    df["JalaliYear"] = pd.to_numeric(
        df["JalaliYear"],
        errors="coerce"
    )

    return df


def extract_city_gas(
    gas_df,
    city_name,
):

    city_name = normalize_text(
        city_name
    )

    df = gas_df[
        gas_df["City"] == city_name
    ].copy()

    if df.empty:
        raise ValueError(
            f"No gas data for city: {city_name}"
        )

    return df


def gas_to_monthly(
    city_gas,
):

    month_columns = {}

    for column in city_gas.columns:

        normalized = normalize_text(
            column
        )

        if normalized in MONTH_MAP:
            month_columns[column] = (
                MONTH_MAP[normalized]
            )

    if len(month_columns) != 12:
        raise ValueError(
            "Not all 12 gas month columns "
            f"were found: {month_columns}"
        )

    records = []

    for column, month in month_columns.items():

        temp = city_gas[
            [
                "JalaliYear",
                column,
            ]
        ].copy()

        temp = temp.rename(
            columns={
                column: "Gas_m3"
            }
        )

        temp["JalaliMonth"] = month

        records.append(temp)

    result = pd.concat(
        records,
        ignore_index=True
    )

    result["Gas_m3"] = pd.to_numeric(
        result["Gas_m3"],
        errors="coerce"
    ).fillna(0)

    return (
        result
        .groupby(
            [
                "JalaliYear",
                "JalaliMonth",
            ],
            as_index=False,
        )["Gas_m3"]
        .sum()
    )