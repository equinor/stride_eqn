"""Stride configuration utilities.

Manages the Stride configuration directory (``~/.stride/``) and configuration
file (``~/.stride/config.json``).
"""

import json
from pathlib import Path
from typing import Any


def get_stride_config_dir() -> Path:
    """Get the stride configuration directory, creating it if necessary.

    Returns
    -------
    Path
        Path to ~/.stride/
    """
    config_dir = Path.home() / ".stride"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_stride_config_path() -> Path:
    """Get the stride configuration file path.

    Returns
    -------
    Path
        Path to ~/.stride/config.json
    """
    return get_stride_config_dir() / "config.json"


def load_stride_config() -> dict[str, Any]:
    """Load the stride configuration file.

    Returns
    -------
    dict[str, Any]
        Configuration dictionary, or empty dict if file doesn't exist
    """
    config_path = get_stride_config_path()
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        result: dict[str, Any] = json.load(f)
        return result


def save_stride_config(config: dict[str, Any]) -> None:
    """Save the stride configuration file.

    Parameters
    ----------
    config : dict[str, Any]
        Configuration dictionary to save
    """
    config_path = get_stride_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def get_max_cached_projects() -> int | None:
    """Get the max cached projects setting from config.

    Returns
    -------
    int | None
        Configured max cached projects, or None if not set
    """
    config = load_stride_config()
    value = config.get("max_cached_projects")
    if value is not None:
        return int(value)
    return None


def set_max_cached_projects(n: int) -> None:
    """Set the max cached projects in the config file.

    Parameters
    ----------
    n : int
        Number of max cached projects (will be clamped to [1, 10])
    """
    n = max(1, min(10, n))
    config = load_stride_config()
    config["max_cached_projects"] = n
    save_stride_config(config)
