from pathlib import Path

import numpy as np
import pandas as pd


def normalize_text(value):
    if pd.isna(value):
        return ""

    value = str(value)

    replacements = {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ۀ": "ه",
        "\u200c": " ",
        "\u00a0": " ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return " ".join(value.split()).strip()


def haversine_km(lat1, lon1, lat2, lon2):

    r = 6371.0

    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)

    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    return 2 * r * np.arcsin(np.sqrt(a))


def find_column(df, candidates):

    normalized = {
        normalize_text(c): c
        for c in df.columns
    }

    for candidate in candidates:
        key = normalize_text(candidate)

        if key in normalized:
            return normalized[key]

    return None


def load_city_coordinates(path):

    df = pd.read_excel(path)

    lat_col = find_column(
        df,
        ["Latitude"]
    )

    lon_col = find_column(
        df,
        ["Longitude"]
    )

    city_col = find_column(
        df,
        ["city", "شهر"]
    )

    province_col = find_column(
        df,
        ["province", "استان"]
    )

    required = [
        lat_col,
        lon_col,
        city_col,
        province_col,
    ]

    if any(x is None for x in required):
        raise ValueError(
            "Required city coordinate columns not found."
        )

    df = df.rename(
        columns={
            lat_col: "Latitude",
            lon_col: "Longitude",
            city_col: "City",
            province_col: "Province",
        }
    )

    df["City"] = df["City"].apply(
        normalize_text
    )

    df["Province"] = df["Province"].apply(
        normalize_text
    )

    df["Latitude"] = pd.to_numeric(
        df["Latitude"],
        errors="coerce"
    )

    df["Longitude"] = pd.to_numeric(
        df["Longitude"],
        errors="coerce"
    )

    return df.dropna(
        subset=[
            "Latitude",
            "Longitude"
        ]
    )


def find_nearest_city(
    city_df,
    latitude,
    longitude,
):

    df = city_df.copy()

    df["Distance_km"] = haversine_km(
        latitude,
        longitude,
        df["Latitude"].values,
        df["Longitude"].values,
    )

    return (
        df.sort_values("Distance_km")
        .iloc[0]
    )


def load_substations(path):

    df = pd.read_parquet(path)

    required = [
        "UniqueCode",
        "Lat",
        "Lon",
        "Voltage",
        "StationType",
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing substation columns: {missing}"
        )

    df["Voltage"] = (
        df["Voltage"]
        .astype(str)
        .str.strip()
    )

    df["StationType"] = pd.to_numeric(
        df["StationType"],
        errors="coerce"
    )

    df["Lat"] = pd.to_numeric(
        df["Lat"],
        errors="coerce"
    )

    df["Lon"] = pd.to_numeric(
        df["Lon"],
        errors="coerce"
    )

    return df.dropna(
        subset=["Lat", "Lon"]
    )


def find_city_substations(
    substations,
    city,
    voltage="63-66",
    station_type=42,
    radius_km=5.0,
):

    candidates = substations[
        (substations["Voltage"] == voltage)
        &
        (
            substations["StationType"]
            == station_type
        )
    ].copy()

    candidates["CityDistance_km"] = haversine_km(
        city["Latitude"],
        city["Longitude"],
        candidates["Lat"].values,
        candidates["Lon"].values,
    )

    return (
        candidates[
            candidates["CityDistance_km"]
            <= radius_km
        ]
        .sort_values("CityDistance_km")
        .copy()
    )