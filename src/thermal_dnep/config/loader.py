from pathlib import Path
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config(config_path=None):
    """
    Load project configuration from YAML.

    Parameters
    ----------
    config_path : str or Path, optional
        Path to config.yaml. If None, project root config is used.

    Returns
    -------
    dict
        Configuration dictionary.
    """
    if config_path is None:
        config_path = PROJECT_ROOT / "config.yaml"

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    return config