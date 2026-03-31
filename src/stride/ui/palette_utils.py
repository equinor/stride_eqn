"""Utility functions for managing user palettes.

Provides functions for saving, loading, and listing user palettes stored
in ``~/.stride/palettes/``, as well as managing palette-related settings
(default palette, palette priority) in the Stride configuration file.
"""

import json
from pathlib import Path

from stride.config import (
    load_stride_config,
    save_stride_config,
)
from stride.ui.palette import ColorPalette


def get_user_palette_dir() -> Path:
    """Get the user's palette directory, creating it if necessary.

    Returns
    -------
    Path
        Path to ~/.stride/palettes/
    """
    palette_dir = Path.home() / ".stride" / "palettes"
    palette_dir.mkdir(parents=True, exist_ok=True)
    return palette_dir


def list_user_palettes() -> list[Path]:
    """List all user palettes.

    Returns
    -------
    list[Path]
        List of paths to user palette files
    """
    palette_dir = get_user_palette_dir()
    return sorted(palette_dir.glob("*.json"))


def save_user_palette(name: str, palette: dict[str, str] | dict[str, dict[str, str]]) -> Path:
    """Save a palette to the user's palette directory.

    Parameters
    ----------
    name : str
        Name for the palette (will be used as filename)
    palette : dict[str, str] | dict[str, dict[str, str]]
        Palette dictionary to save (either flat or structured format)

    Returns
    -------
    Path
        Path to the saved palette file
    """
    palette_dir = get_user_palette_dir()
    palette_path = palette_dir / f"{name}.json"

    data = {
        "name": name,
        "palette": palette,
    }

    with open(palette_path, "w") as f:
        json.dump(data, f, indent=2)

    return palette_path


def load_user_palette(name: str) -> ColorPalette:
    """Load a user palette by name.

    Parameters
    ----------
    name : str
        Name of the palette to load

    Returns
    -------
    ColorPalette
        Loaded color palette

    Raises
    ------
    FileNotFoundError
        If the palette does not exist
    """
    palette_dir = get_user_palette_dir()
    palette_path = palette_dir / f"{name}.json"

    if not palette_path.exists():
        msg = f"User palette '{name}' not found"
        raise FileNotFoundError(msg)

    with open(palette_path) as f:
        data = json.load(f)
        # Handle both nested {"palette": {...}} and flat {...} structures
        if isinstance(data, dict):
            if "palette" in data:
                palette_dict = data["palette"]
            else:
                palette_dict = data
        else:
            msg = f"Invalid palette format in {name}.json"
            raise ValueError(msg)

    return ColorPalette.from_dict(palette_dict)


def delete_user_palette(name: str) -> None:
    """Delete a user palette by name.

    Parameters
    ----------
    name : str
        Name of the palette to delete

    Raises
    ------
    FileNotFoundError
        If the palette does not exist
    """
    palette_dir = get_user_palette_dir()
    palette_path = palette_dir / f"{name}.json"

    if not palette_path.exists():
        msg = f"User palette '{name}' not found"
        raise FileNotFoundError(msg)

    palette_path.unlink()


def set_default_user_palette(name: str | None) -> None:
    """Set the default user palette.

    Parameters
    ----------
    name : str | None
        Name of the user palette to set as default, or None to clear the default
    """
    config = load_stride_config()

    if name is None:
        config.pop("default_user_palette", None)
    else:
        # Verify the palette exists
        palette_dir = get_user_palette_dir()
        palette_path = palette_dir / f"{name}.json"
        if not palette_path.exists():
            msg = f"User palette '{name}' not found at {palette_path}"
            raise FileNotFoundError(msg)
        config["default_user_palette"] = name

    save_stride_config(config)


def get_default_user_palette() -> str | None:
    """Get the default user palette name.

    Returns
    -------
    str | None
        Name of the default user palette, or None if not set
    """
    config = load_stride_config()
    return config.get("default_user_palette")


def set_palette_priority(priority: str) -> None:
    """Set the palette priority for dashboard launch.

    Parameters
    ----------
    priority : str
        Priority setting: "user" to prefer user palette, "project" to prefer project palette
    """
    if priority not in ("user", "project"):
        msg = f"Invalid palette priority: {priority!r}. Must be 'user' or 'project'."
        raise ValueError(msg)
    config = load_stride_config()
    config["palette_priority"] = priority
    save_stride_config(config)


def get_palette_priority() -> str:
    """Get the palette priority for dashboard launch.

    Returns
    -------
    str
        Priority setting: "user" or "project". Defaults to "user".
    """
    config = load_stride_config()
    return str(config.get("palette_priority", "user"))
