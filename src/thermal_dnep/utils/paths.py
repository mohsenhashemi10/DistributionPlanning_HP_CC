from pathlib import Path


def create_project_directories(config):
    """
    Create directories defined in project configuration.
    """

    for path_value in config["paths"].values():
        path = Path(path_value)
        path.mkdir(parents=True, exist_ok=True)