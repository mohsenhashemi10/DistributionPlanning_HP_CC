from pathlib import Path
import sys

import pandas as pd


# ============================================================
# PROJECT
# ============================================================

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src")
)


# ============================================================
# IMPORTS
# ============================================================
from thermal_dnep.utils.city_boundary import (
    get_city_boundary,
    classify_points_in_city,
    in_city
)


from thermal_dnep.thermal.city_matching import (
    load_city_coordinates,
    find_nearest_city,
    load_substations,
    find_city_substations,
)

from thermal_dnep.thermal.gas_processing import (
    load_gas_data,
    extract_city_gas,
    gas_to_monthly,
)

from thermal_dnep.thermal.thermal_conversion import (
    estimate_thermal_gas,
    convert_gas_to_thermal_energy,
)

from thermal_dnep.thermal.feeder_allocation import (
    calculate_feeder_cooling_shares,
    allocate_heating_to_feeders,
    validate_feeder_allocation,
)

from thermal_dnep.weather.city_weather import (
    get_city_weather,
)

from thermal_dnep.utils.dates import (
    gregorian_to_jalali_year_month,
)
# ============================================================
# CONFIG
# ============================================================

SUBSTATION_CODE = "TAZB"

SUBSTATION_LAT = 35.6996
SUBSTATION_LON = 51.3675

CITY_COORD_FILE = (
    PROJECT_ROOT
    / "data/raw/gas"
    / "CityGasUTM_Compelete_final.xlsx"
)

GAS_FILE = (
    PROJECT_ROOT
    / "data/raw/gas"
    / "GasData_EnergyInstitute_final.xlsx"
)

SUBSTATIONS_FILE = (
    PROJECT_ROOT
    / "data/raw/substations"
    / "df_AllSubstationsNonZero.parquet"
)

COOLING_FILE = (
    PROJECT_ROOT
    / "data/processed/stage3/cooling"
    / "tazb_cooling_estimation.parquet"
)

WEATHER_DIR = (
    PROJECT_ROOT
    / "data/raw/weather"
)

WEATHER_CACHE = (
    PROJECT_ROOT
    / "data/raw/weather/cache"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data/processed/stage4/thermal"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("STAGE 4 - GAS BASED THERMAL LOAD ESTIMATION")
    print("=" * 70)

    # --------------------------------------------------------
    # 1. City matching
    # --------------------------------------------------------

    cities = load_city_coordinates(
        CITY_COORD_FILE
    )

    city = find_nearest_city(
        cities,
        SUBSTATION_LAT,
        SUBSTATION_LON,
    )

    print(
        f"\nTarget substation : {SUBSTATION_CODE}"
    )

    print(
        f"Matched city      : {city['City']}"
    )

    print(
        f"Province          : {city['Province']}"
    )

    print(
        f"Distance           : "
        f"{city['Distance_km']:.2f} km"
    )

    # --------------------------------------------------------
    # 2. Substations
    # --------------------------------------------------------

    substations = load_substations(
        SUBSTATIONS_FILE
    )

    # city_substations = find_city_substations(
    #     substations,
    #     city,
    # )

    city_substations = in_city(
        substations,
        city.City,
    )

    target = city_substations[
        city_substations["UniqueCode"]
        .astype(str)
        .str.upper()
        == SUBSTATION_CODE
    ]

    if target.empty:
        raise ValueError(
            f"{SUBSTATION_CODE} not found."
        )

    print(
        f"\nCity substations: "
        f"{len(city_substations)}"
    )

    # --------------------------------------------------------
    # 3. Gas
    # --------------------------------------------------------

    gas = load_gas_data(
        GAS_FILE
    )

    city_gas = extract_city_gas(
        gas,
        city["City"],
    )

    gas_monthly = gas_to_monthly(
        city_gas
    )
    
    gas_monthly['Gas_m3']=gas_monthly['Gas_m3']/(1+city_substations.shape[0])
    # --------------------------------------------------------
    # 4. Weather
    # --------------------------------------------------------

    min_year = int(
        gas_monthly["JalaliYear"].min()
    )

    max_year = int(
        gas_monthly["JalaliYear"].max()
    )

    # For the first implementation we use the full
    # Gregorian period corresponding to the gas dataset.

    weather = get_city_weather(
        latitude=city["Latitude"],
        longitude=city["Longitude"],
        start_date="2014-03-21",
        end_date="2025-03-20",
        weather_dir=WEATHER_DIR,
        cache_dir=WEATHER_CACHE,
    )

    # --------------------------------------------------------
    # 5. Convert weather dates to Jalali calendar
    # --------------------------------------------------------

    weather = weather.copy()

    weather["Timestamp"] = pd.to_datetime(
        weather["Timestamp"]
    )

    jalali_dates = (
        weather["Timestamp"]
        .apply(gregorian_to_jalali_year_month)
    )

    weather["JalaliYear"] = (
        jalali_dates
        .apply(lambda x: x[0])
    )

    weather["JalaliMonth"] = (
        jalali_dates
        .apply(lambda x: x[1])
    )


    # --------------------------------------------------------
    # 6. Monthly temperature
    # --------------------------------------------------------

    monthly_temperature = (
        weather
        .groupby(
            [
                "JalaliYear",
                "JalaliMonth",
            ],
            as_index=False,
        )
        .agg(
            MeanTemperature=(
                "Temperature",
                "mean",
            ),
            MeanHumidity=(
                "RelativeHumidity",
                "mean",
            ),
            MeanSolarRadiation=(
                "SolarRadiation",
                "mean",
            ),
        )
    )

    # --------------------------------------------------------
    # 6. Gas -> thermal
    # --------------------------------------------------------

    thermal = estimate_thermal_gas(
        gas_monthly,
        monthly_temperature,
    )

    thermal = convert_gas_to_thermal_energy(
        thermal
    )

    # --------------------------------------------------------
    # 7. Cooling-based feeder allocation
    # --------------------------------------------------------

    cooling = pd.read_parquet(
        COOLING_FILE
    )

    cooling_shares = (
        calculate_feeder_cooling_shares(
            cooling
        )
    )

    # --------------------------------------------------------
    # 8. Target substation
    # --------------------------------------------------------

    # Stage 3 cooling represents the target
    # substation. Therefore the extracted city thermal
    # profile is applied to this substation.

    thermal["SubstationCode"] = (
        SUBSTATION_CODE
    )

    # --------------------------------------------------------
    # 9. Allocate thermal load to feeders
    # --------------------------------------------------------

    allocated = (
        allocate_heating_to_feeders(
            thermal,
            cooling_shares,
        )
    )

    # --------------------------------------------------------
    # 10. Validation
    # --------------------------------------------------------

    validation = (
        validate_feeder_allocation(
            allocated
        )
    )

    print(
        "\nMaximum allocation error:",
        validation["RelativeError"]
        .abs()
        .max()
    )

    # --------------------------------------------------------
    # 11. Save
    # --------------------------------------------------------

    thermal.to_parquet(
        OUTPUT_DIR
        / "TAZB_city_thermal.parquet",
        index=False,
    )

    cooling_shares.to_parquet(
        OUTPUT_DIR
        / "TAZB_cooling_shares.parquet",
        index=False,
    )

    allocated.to_parquet(
        OUTPUT_DIR
        / "TAZB_feeder_heating.parquet",
        index=False,
    )

    validation.to_csv(
        OUTPUT_DIR
        / "TAZB_allocation_validation.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "\nOutputs saved to:"
    )

    print(
        OUTPUT_DIR
    )

    print("\nSTAGE 4 COMPLETED.")


if __name__ == "__main__":
    main()