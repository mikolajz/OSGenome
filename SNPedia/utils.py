from pathlib import Path


def get_app_dir() -> Path:
    return Path(__file__).parent


def get_default_data_dir() -> Path:
    return get_app_dir() / "data"
