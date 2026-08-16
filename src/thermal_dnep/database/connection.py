import pyodbc


def create_connection(config):
    """
    Create SQL Server connection using configuration.

    Parameters
    ----------
    config : dict
        Project configuration.

    Returns
    -------
    pyodbc.Connection
    """

    db_config = config["database"]

    server = db_config["server"]
    database = db_config["database"]
    driver = db_config["driver"]

    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"Trusted_Connection=yes;"
    )

    return pyodbc.connect(connection_string)