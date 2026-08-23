from pathlib import Path

import pandas as pd

from thermal_dnep.database.connection import create_connection
from thermal_dnep.database.queries import FEEDER_QUERY


def load_feeder_data(config, station_code=None):
    """
    Load feeder energy data from SQL Server.

    Parameters
    ----------
    config : dict
        Project configuration.
    station_code : str, optional
        Substation code.

    Returns
    -------
    pandas.DataFrame
    """

    if station_code is None:
        station_code = config["feeder"]["station_code"]

    connection = create_connection(config)

    try:
        df = pd.read_sql(
            FEEDER_QUERY,
            connection,
            params=[station_code]
        )
    finally:
        connection.close()

    return df


def save_raw_feeder_data(df, config, station_code=None):
    """
    Save raw feeder data as CSV.
    """

    if station_code is None:
        station_code = config["feeder"]["station_code"]

    output_dir = Path(config["paths"]["raw_data"]) / "feeder"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{station_code}.csv"

    df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    return output_file