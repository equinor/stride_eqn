"""
Utilities for managing color palettes for the Stride UI.

The :class:`~stride.ui.palette.ColorPalette` class stores colors as hex strings and automatically
supplies new colors. All color inputs are checked for valid hex string representation and new colors are provided
if a color input is invalid.

The class provides a class method to intialize a palette from a dictionary while sanitizing each input entry.
"""

import re
from enum import StrEnum
from itertools import cycle
from typing import Any, Mapping, MutableSequence, TypedDict


# can have a project color palette, or a user color palette?
# can toggle between project and use color palette?
#
# Might be simplest just to have project color palette and save
# it into the project json file.

hex_color_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$|^#[0-9A-Fa-f]{8}$")
rgb_color_pattern = re.compile(r"^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)$")


class ColorCategory(StrEnum):
    """Categories for color palette entries.

    ``SECTOR`` and ``END_USE`` share the same colour theme but maintain
    independent iterators so each group starts from position 0.
    """

    SCENARIO = "scenarios"
    MODEL_YEAR = "model_years"
    SECTOR = "sector"
    END_USE = "end_use"


# ============================================================================
# Paul Tol color-blind-safe palettes
# Source: https://sronpersonalpages.nl/~pault/
# ============================================================================

# Scenarios: Tol Bright (7 colors) — primary qualitative, color-blind safe
TOL_BRIGHT = [
    "#4477AA",  # blue
    "#CCBB44",  # yellow
    "#228833",  # green
    "#EE6677",  # red
    "#66CCEE",  # cyan
    "#AA3377",  # purple
    "#BBBBBB",  # grey
]

# Metrics (light mode): dark-enough colors from Tol Muted + Discrete Rainbow 14
TOL_METRICS_LIGHT = [
    "#CC6677",  # muted rose
    "#999933",  # muted olive
    "#5289C7",  # DR14 med blue
    "#117733",  # muted green
    "#882255",  # muted wine
    "#1965B0",  # DR14 blue
    "#E8601C",  # DR14 red-orange
    "#332288",  # muted indigo
    "#AA4499",  # muted purple
    "#DC050C",  # DR14 red
    "#AE76A3",  # DR14 mauve
    "#882E72",  # DR14 dk purple
]

# Metrics (dark mode): light-enough colors from Tol Muted + Discrete Rainbow 14
TOL_METRICS_DARK = [
    "#CC6677",  # muted rose
    "#DDCC77",  # muted sand
    "#88CCEE",  # muted cyan
    "#44AA99",  # muted teal
    "#AA4499",  # muted purple
    "#5289C7",  # DR14 med blue
    "#999933",  # muted olive
    "#F4A736",  # DR14 orange
    "#90C987",  # DR14 lt green
    "#D1BBD7",  # DR14 lavender
    "#AE76A3",  # DR14 mauve
    "#7BAFDE",  # DR14 lt blue
    "#E8601C",  # DR14 red-orange
    "#DDDDDD",  # muted pale grey
    "#DC050C",  # DR14 red
    "#117733",  # muted green
]

# Model years: Tol Iridescent (23 colors, sequential, designed for interpolation)
TOL_IRIDESCENT = [
    "#FEFBE9",  # idx  0
    "#FCF7D5",  # idx  1
    "#F5F3C1",  # idx  2
    "#EAF0B5",  # idx  3
    "#DDECBF",  # idx  4
    "#D0E7CA",  # idx  5
    "#C2E3D2",  # idx  6
    "#B5DDD8",  # idx  7
    "#A8D8DC",  # idx  8
    "#9BD2E1",  # idx  9
    "#8DCBE4",  # idx 10
    "#81C4E7",  # idx 11
    "#7BBCE7",  # idx 12
    "#7EB2E4",  # idx 13
    "#88A5DD",  # idx 14
    "#9398D2",  # idx 15
    "#9B8AC4",  # idx 16
    "#9D7DB2",  # idx 17
    "#9A709E",  # idx 18
    "#906388",  # idx 19
    "#805770",  # idx 20
    "#684957",  # idx 21
    "#46353A",  # idx 22
]

# WCAG-derived usable index ranges for Iridescent (3.0:1 contrast threshold)
IRIDESCENT_LIGHT_START = 16  # First index passing 3:1 on #FFFFFF
IRIDESCENT_LIGHT_END = 22  # Last index (inclusive)
IRIDESCENT_DARK_START = 0  # First index passing 3:1 on #1A1A1A
IRIDESCENT_DARK_END = 19  # Last index passing 3:1 on #1A1A1A


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB values to hex color string."""
    return f"#{r:02X}{g:02X}{b:02X}"


def _interpolate_hex(color1: str, color2: str, t: float) -> str:
    """Linearly interpolate between two hex colors.

    Parameters
    ----------
    color1 : str
        Start color (hex)
    color2 : str
        End color (hex)
    t : float
        Interpolation factor, 0.0 = color1, 1.0 = color2
    """
    r1, g1, b1 = _hex_to_rgb(color1)
    r2, g2, b2 = _hex_to_rgb(color2)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return _rgb_to_hex(r, g, b)


def sample_iridescent(n: int, theme: str = "light") -> list[str]:
    """Sample n evenly-spaced colors from the Tol Iridescent ramp.

    Uses the WCAG-safe index range for the given theme, and linearly
    interpolates between defined colors when more colors are needed
    than available in the usable range.

    Parameters
    ----------
    n : int
        Number of colors to produce
    theme : str
        ``"light"`` or ``"dark"`` — selects the usable index range

    Returns
    -------
    list[str]
        List of n hex color strings
    """
    if theme == "dark":
        start, end = IRIDESCENT_DARK_START, IRIDESCENT_DARK_END
    else:
        start, end = IRIDESCENT_LIGHT_START, IRIDESCENT_LIGHT_END

    if n <= 0:
        return []
    if n == 1:
        mid = (start + end) // 2
        return [TOL_IRIDESCENT[mid]]

    # Generate n evenly-spaced positions in the continuous [start, end] range
    positions = [start + i * (end - start) / (n - 1) for i in range(n)]
    result = []
    for pos in positions:
        idx_low = int(pos)
        idx_high = min(idx_low + 1, len(TOL_IRIDESCENT) - 1)
        if idx_low == idx_high:
            result.append(TOL_IRIDESCENT[idx_low])
        else:
            t = pos - idx_low
            result.append(_interpolate_hex(TOL_IRIDESCENT[idx_low], TOL_IRIDESCENT[idx_high], t))
    return result


class PaletteItem(TypedDict):
    """Structure for a palette item with label, color, and order."""

    label: str
    color: str
    order: int


class ColorPalette:
    """Represents a color palette for use in the Stride UI.

    Provides methods to update, get, and pop colors by a key entry.
    Keys typically map to label values in a stack chart or chart label.
    """

    def __init__(
        self,
        *,
        scenario_theme: list[str] | None = None,
        model_year_theme: list[str] | None = None,
        metric_theme: list[str] | None = None,
    ):
        """Create an empty palette with the given color themes.

        Use :meth:`load` to construct a palette from serialized data.

        Parameters
        ----------
        scenario_theme : list[str] | None
            Custom color cycle for scenarios.  Defaults to :data:`TOL_BRIGHT`.
        model_year_theme : list[str] | None
            Custom color cycle for model years.  Defaults to :data:`TOL_IRIDESCENT`.
        metric_theme : list[str] | None
            Custom color cycle for sectors and end uses.  Defaults to
            :data:`TOL_METRICS_LIGHT`.
        """
        # Color-blind-safe themes (Paul Tol palettes) — overridable
        self.scenario_theme: list[str] = list(scenario_theme or TOL_BRIGHT)
        self.model_year_theme: list[str] = list(model_year_theme or TOL_IRIDESCENT)
        self.metric_theme: list[str] = list(metric_theme or TOL_METRICS_LIGHT)
        self._ui_theme: str = "light"  # "light" or "dark"

        self._scenario_iterator = cycle(self.scenario_theme)
        self._model_year_iterator = cycle(self.model_year_theme)
        self._sector_iterator = cycle(self.metric_theme)
        self._end_use_iterator = cycle(self.metric_theme)

        # Separate palettes for each category
        self.scenarios: dict[str, str] = {}
        self.model_years: dict[str, str] = {}
        self.sectors: dict[str, str] = {}
        self.end_uses: dict[str, str] = {}

    @property
    def palette(self) -> dict[str, str]:
        """Return a merged dictionary of all colors for backward compatibility.

        Returns
        -------
        dict[str, str]
            A flat dictionary combining all categories (scenarios, model_years, metrics).
        """
        result = {}
        result.update(self.scenarios)
        result.update(self.model_years)
        result.update(self.sectors)
        result.update(self.end_uses)
        return result

    def __str__(self) -> str:
        """Return a string representation of the palette."""
        num_scenarios = len(self.scenarios)
        num_model_years = len(self.model_years)
        num_sectors = len(self.sectors)
        num_end_uses = len(self.end_uses)
        return (
            f"ColorPalette(scenarios={num_scenarios}, model_years={num_model_years}, "
            f"sectors={num_sectors}, end_uses={num_end_uses})"
        )

    def __repr__(self) -> str:
        """Return a detailed string representation of the palette."""
        return self.__str__()

    @property
    def has_custom_themes(self) -> bool:
        """Return ``True`` if any theme differs from the built-in defaults."""
        return (
            self.scenario_theme != list(TOL_BRIGHT)
            or self.model_year_theme != list(TOL_IRIDESCENT)
            or self.metric_theme != list(TOL_METRICS_LIGHT)
        )

    def copy(self) -> "ColorPalette":
        """Create a deep copy of this ColorPalette.

        Returns
        -------
        ColorPalette
            A new ColorPalette instance with the same colors and structure.
        """
        return ColorPalette.from_dict(self.to_dict())

    # -- Helper methods (used by update / get / pop / set_ui_theme) -----------

    @staticmethod
    def _is_valid_color(color: str | None) -> bool:
        """Return ``True`` if *color* is a recognised hex or rgb/rgba string."""
        return isinstance(color, str) and bool(
            hex_color_pattern.match(color) or rgb_color_pattern.match(color)
        )

    def _get_target(self, category: ColorCategory) -> tuple[dict[str, str], Any]:
        """Return ``(color_dict, iterator)`` for *category*."""
        _map = {
            ColorCategory.SCENARIO: (self.scenarios, self._scenario_iterator),
            ColorCategory.MODEL_YEAR: (self.model_years, self._model_year_iterator),
            ColorCategory.SECTOR: (self.sectors, self._sector_iterator),
            ColorCategory.END_USE: (self.end_uses, self._end_use_iterator),
        }
        return _map[category]

    def _resolve_str_category(
        self,
        category: "ColorCategory | str | None",
    ) -> "ColorCategory | None":
        """Convert a plain string to :class:`ColorCategory`, passing through ``None``."""
        if category is None or isinstance(category, ColorCategory):
            return category
        return ColorCategory(category)

    def _sort_model_years(self) -> None:
        """Re-sort model-year entries in chronological order (in-place)."""
        sorted_items = sorted(
            self.model_years.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0
        )
        self.model_years.clear()
        self.model_years.update(sorted_items)

    def _reassign_and_reset(
        self,
        category: ColorCategory,
        auto_colors: set[str] | None = None,
    ) -> None:
        """Re-colour entries in *category* from position 0 and reset its iterator.

        Parameters
        ----------
        auto_colors : set[str] | None
            When provided, only colours that appear in this set are
            overwritten; all others are treated as user-customised and
            preserved.  Pass ``None`` to overwrite everything (legacy
            behaviour used by ``reset_to_defaults``).
        """
        target_dict, _ = self._get_target(category)
        fresh = cycle(self.metric_theme)
        for key in target_dict:
            new_color = next(fresh)
            if auto_colors is None or target_dict[key] in auto_colors:
                target_dict[key] = new_color
            # else: preserve user-customised colour
        # Reset iterator, advanced past assigned entries
        new_iter = cycle(self.metric_theme)
        for _ in range(len(target_dict)):
            next(new_iter)
        if category == ColorCategory.SECTOR:
            self._sector_iterator = new_iter
        else:
            self._end_use_iterator = new_iter

    # -- Public API -----------------------------------------------------------

    def update(
        self,
        key: str,
        color: str | None = None,
        *,
        category: ColorCategory | str,
    ) -> None:
        """Update or create a color for the given *key*.

        Keys are normalized to lowercase for consistent lookups.

        Parameters
        ----------
        key : str
            The lookup key for which to assign or update the color.
        color : str | None, optional
            A hex or rgb/rgba color string.  If ``None`` or invalid a new
            color is assigned from the category's theme.
        category : ColorCategory | str
            Target category (required).
        """
        if not isinstance(key, str):
            msg = "ColorPalette: Key must be a string"
            raise TypeError(msg)

        key = key.lower()
        resolved = self._resolve_str_category(category)
        if resolved is None:
            msg = "ColorPalette.update() requires a valid category"
            raise ValueError(msg)
        target_dict, iterator = self._get_target(resolved)
        target_dict[key] = color if self._is_valid_color(color) else next(iterator)

        if resolved == ColorCategory.MODEL_YEAR:
            self._sort_model_years()

    def get(self, key: str, category: ColorCategory | str | None = None) -> str:
        """Return the color for *key*, generating one if it does not exist.

        Keys are normalized to lowercase.  Searches across all categories
        unless *category* is specified.

        Parameters
        ----------
        key : str
            The lookup key.
        category : ColorCategory | str | None, optional
            Specific category to search / store into.
        """
        key = key.lower()
        resolved = self._resolve_str_category(category)

        if resolved is not None:
            target_dict, _ = self._get_target(resolved)
            if key in target_dict:
                return target_dict[key]
        else:
            for cat in ColorCategory:
                d, _ = self._get_target(cat)
                if key in d:
                    return d[key]

        # Generate a new color
        effective = resolved or ColorCategory.SECTOR
        target_dict, iterator = self._get_target(effective)
        color = next(iterator)
        target_dict[key] = color
        return color

    def pop(self, key: str, *, category: ColorCategory | str) -> str:
        """Remove *key* from the palette and return its color.

        Parameters
        ----------
        key : str
            Key to remove.
        category : ColorCategory | str
            Category to remove from (required).

        Raises
        ------
        KeyError
            If *key* is not found.
        """
        key = key.lower()
        resolved = self._resolve_str_category(category)
        if resolved is None:
            msg = "ColorPalette.pop() requires a valid category"
            raise ValueError(msg)

        d, _ = self._get_target(resolved)
        if key in d:
            return d.pop(key)

        msg = f"ColorPalette: unable to remove key: {key}"
        raise KeyError(msg)

    def set_ui_theme(self, theme: str) -> None:
        """Switch palettes for the given UI theme (``"light"`` or ``"dark"``).

        Updates the metric theme, re-assigns sector/end-use colours, and
        re-samples Iridescent colours for model years.  Colours that have
        been manually customised (i.e. do not appear in the old metric
        theme) are preserved.
        """
        if theme not in ("light", "dark"):
            msg = f"Invalid UI theme: {theme!r}. Must be 'light' or 'dark'."
            raise ValueError(msg)

        # Remember old theme colours so we can detect custom assignments
        old_auto_colors = set(self.metric_theme)

        self._ui_theme = theme
        self.metric_theme = list(TOL_METRICS_LIGHT if theme == "light" else TOL_METRICS_DARK)

        # Re-assign sector and end-use colours, preserving custom ones
        self._reassign_and_reset(ColorCategory.SECTOR, old_auto_colors)
        self._reassign_and_reset(ColorCategory.END_USE, old_auto_colors)

        # Re-sample model year colours
        n_years = len(self.model_years)
        if n_years > 0:
            new_colors = sample_iridescent(n_years, theme=theme)
            for (key, _), color in zip(list(self.model_years.items()), new_colors):
                self.model_years[key] = color

        self.model_year_theme = list(TOL_IRIDESCENT)
        self._model_year_iterator = cycle(self.model_year_theme)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColorPalette":  # noqa: C901
        """Construct a :class:`ColorPalette` from a serialized dictionary.

        Accepts three on-disk shapes:

        * **Structured (current)** — top-level keys ``scenarios``,
          ``model_years``, ``sectors``, ``end_uses`` (each mapping
          names to hex colors).  Optionally includes a ``themes`` key
          with per-category color-cycle overrides ("full" palette).
        * **Legacy structured** — ``scenarios``, ``model_years``, and
          ``metrics`` (the old 3-key format).
        * **Legacy flat** — a single-level ``{name: color}`` dict.

        When ``themes`` is present the palette is *full*: custom color
        cycles replace the built-in TOL defaults.  Otherwise the palette
        is *minimal* and the TOL defaults are used for any names not
        already assigned a color.

        Parameters
        ----------
        data : dict[str, Any]
            Serialized palette dictionary.

        Returns
        -------
        ColorPalette
            A new populated instance.
        """
        # Extract optional custom themes ("full" palette)
        themes_raw = data.get("themes")
        custom_scenario_theme: list[str] | None = None
        custom_model_year_theme: list[str] | None = None
        custom_metric_theme: list[str] | None = None

        if isinstance(themes_raw, dict):
            st = themes_raw.get("scenarios")
            if isinstance(st, list) and st:
                custom_scenario_theme = st
            myt = themes_raw.get("model_years")
            if isinstance(myt, list) and myt:
                custom_model_year_theme = myt
            # sectors and end_uses share the metric theme; prefer "sectors"
            mt = themes_raw.get("sectors") or themes_raw.get("end_uses")
            if isinstance(mt, list) and mt:
                custom_metric_theme = mt

        new_palette = cls(
            scenario_theme=custom_scenario_theme,
            model_year_theme=custom_model_year_theme,
            metric_theme=custom_metric_theme,
        )

        # Detect structured format — ignore "themes" key for this check
        _category_keys = {"scenarios", "model_years", "metrics", "sectors", "end_uses"}
        category_values = {k: v for k, v in data.items() if k in _category_keys}
        is_structured = bool(category_values) and all(
            isinstance(v, dict) for v in category_values.values()
        )

        if is_structured:
            # Map category names to (target_dict, theme)
            _category_targets: list[tuple[str, dict[str, str], list[str]]] = [
                ("scenarios", new_palette.scenarios, new_palette.scenario_theme),
                ("model_years", new_palette.model_years, new_palette.model_year_theme),
                ("sectors", new_palette.sectors, new_palette.metric_theme),
                ("end_uses", new_palette.end_uses, new_palette.metric_theme),
                ("metrics", new_palette.sectors, new_palette.metric_theme),  # legacy compat
            ]

            for category_name, target_dict, theme in _category_targets:
                category_value = data.get(category_name)
                if not isinstance(category_value, dict):
                    continue

                color_iterator = cycle(theme)

                # Sort model years as integers before processing to ensure proper color gradient
                items = list(category_value.items())
                if category_name == "model_years":
                    items.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0)

                for key, color in items:
                    normalized_key = key.lower()

                    if not (hex_color_pattern.match(color) or rgb_color_pattern.match(color)):
                        color = next(color_iterator)

                    # Skip duplicates (e.g. legacy metrics overlapping with sectors)
                    if normalized_key not in target_dict:
                        target_dict[normalized_key] = color
        else:
            # Legacy flat format - default to sectors
            metric_iterator = cycle(new_palette.metric_theme)
            for key, color_value in data.items():
                if not isinstance(color_value, str):
                    continue
                normalized_key = key.lower()

                if not (
                    hex_color_pattern.match(color_value) or rgb_color_pattern.match(color_value)
                ):
                    color_value = next(metric_iterator)
                new_palette.sectors[normalized_key] = color_value

        return new_palette

    def refresh_category_colors(self, category: ColorCategory | str) -> None:
        """Reassign colors for all items in a category using the correct theme.

        Parameters
        ----------
        category : ColorCategory | str
            The category to refresh.  The legacy string ``"metrics"``
            refreshes both ``SECTOR`` and ``END_USE``.
        """
        resolved = self._resolve_str_category(category)
        if resolved is None:
            return

        target_dict, _ = self._get_target(resolved)
        labels = list(target_dict.keys())
        if resolved == ColorCategory.MODEL_YEAR:
            labels.sort(key=lambda x: int(x) if x.isdigit() else 0)
        target_dict.clear()

        # Reset the iterator for this category
        theme = (
            self.metric_theme
            if resolved in (ColorCategory.SECTOR, ColorCategory.END_USE)
            else (
                self.scenario_theme
                if resolved == ColorCategory.SCENARIO
                else self.model_year_theme
            )
        )
        new_iter = cycle(theme)
        if resolved == ColorCategory.SCENARIO:
            self._scenario_iterator = new_iter
        elif resolved == ColorCategory.MODEL_YEAR:
            self._model_year_iterator = new_iter
        elif resolved == ColorCategory.SECTOR:
            self._sector_iterator = new_iter
        elif resolved == ColorCategory.END_USE:
            self._end_use_iterator = new_iter

        for label in labels:
            self.update(label, category=resolved)

    def merge_with_project_dimensions(
        self,
        scenarios: list[str] | None = None,
        model_years: list[str] | None = None,
        sectors: list[str] | None = None,
        end_uses: list[str] | None = None,
    ) -> None:
        """Merge this palette with a project's actual dimensions.

        For each category the logic is:

        1. **Matched names** — entries present in both the palette and the
           project keep their stored color.
        2. **Reserve collection** — entries in the palette but *not* in the
           project are set aside as reserves.  Their colors are returned to
           the front of the available-color pool so they are reused before
           cycling through the theme.
        3. **New-name assignment** — names the project has but the palette
           does not are assigned colors by drawing first from the reserve
           pool, then from the theme (skipping colors already claimed by
           matched entries).

        After merging, the category dict is reordered so that project-active
        entries come first (in the order given), followed by reserves.

        Parameters
        ----------
        scenarios : list[str] | None
            Scenario names present in the project.
        model_years : list[str] | None
            Model year labels (as strings) present in the project.
        sectors : list[str] | None
            Sector names present in the project.
        end_uses : list[str] | None
            End-use names present in the project.
        """
        _plan: list[tuple[list[str] | None, ColorCategory]] = [
            (scenarios, ColorCategory.SCENARIO),
            (model_years, ColorCategory.MODEL_YEAR),
            (sectors, ColorCategory.SECTOR),
            (end_uses, ColorCategory.END_USE),
        ]

        for project_names, cat in _plan:
            if project_names is None:
                continue
            self._merge_category(project_names, cat)

    def _merge_category(self, project_names: list[str], category: ColorCategory) -> None:
        """Merge a single category with the project's dimension names.

        Order of operations:
        1. Match names present in both palette and project — keep their colors.
        2. Collect reserve entries (palette names not in the project).  Their
           colors are returned to the front of the available-color pool so
           they get reused before cycling through the theme.
        3. Assign colors to new project names by drawing first from reserve
           colors, then from the theme (skipping colors used by matches).
        """
        target_dict, _ = self._get_target(category)

        # Normalize project names
        normalized = [n.lower() for n in project_names]
        project_set = set(normalized)

        # 1. Matched names — in both palette and project
        matched_colors: dict[str, str] = {}
        for name in normalized:
            if name in target_dict:
                matched_colors[name] = target_dict[name]

        used_colors = set(matched_colors.values())

        # 2. Reserve entries — in palette but not in project.
        #    Their colors go back into the available pool (front of the line).
        reserve_entries: dict[str, str] = {
            k: v for k, v in target_dict.items() if k not in project_set
        }
        reserve_colors = [v for v in reserve_entries.values() if v not in used_colors]

        # 3. Build color iterator: reserve colors first, then theme (skipping used)
        if category == ColorCategory.SCENARIO:
            theme = self.scenario_theme
        elif category == ColorCategory.MODEL_YEAR:
            theme = self.model_year_theme
        else:
            theme = self.metric_theme

        def _available_color_iter() -> Any:
            """Yield reserve colors first, then theme colors, skipping used."""
            yield from reserve_colors
            seen_skip: set[str] = set()
            for color in cycle(theme):
                if color in used_colors and color not in seen_skip:
                    seen_skip.add(color)
                    continue
                yield color

        color_iter = _available_color_iter()

        # Assign colors to new (unmatched) project names
        unmatched_names = [n for n in normalized if n not in target_dict]
        new_assignments: dict[str, str] = {}
        for name in unmatched_names:
            new_assignments[name] = next(color_iter)

        # Rebuild the category dict: active entries (in project order),
        # then reserves
        target_dict.clear()
        for name in normalized:
            if name in matched_colors:
                target_dict[name] = matched_colors[name]
            else:
                target_dict[name] = new_assignments[name]
        target_dict.update(reserve_entries)

        # Reset the iterator, advanced past the assigned entries
        new_iter = cycle(theme)
        for _ in range(len(target_dict)):
            next(new_iter)
        if category == ColorCategory.SCENARIO:
            self._scenario_iterator = new_iter
        elif category == ColorCategory.MODEL_YEAR:
            self._model_year_iterator = new_iter
        elif category == ColorCategory.SECTOR:
            self._sector_iterator = new_iter
        elif category == ColorCategory.END_USE:
            self._end_use_iterator = new_iter

        if category == ColorCategory.MODEL_YEAR:
            self._sort_model_years()

    def get_display_items(
        self, category: ColorCategory | str | None = None
    ) -> dict[str, list[tuple[str, str, str]]]:
        """Get palette items formatted for display with proper capitalization.

        Returns tuples of (display_label, lowercase_key, color) for each item.
        """
        resolved = self._resolve_str_category(category) if category is not None else None

        def _fmt(d: dict[str, str]) -> list[tuple[str, str, str]]:
            return [(k.capitalize(), k, c) for k, c in d.items()]

        groups: dict[str, dict[str, str]] = {
            "scenarios": self.scenarios,
            "model_years": self.model_years,
            "sectors": self.sectors,
            "end_uses": self.end_uses,
        }

        if resolved is None:
            return {name: _fmt(d) for name, d in groups.items() if d}

        _cat_to_group = {
            ColorCategory.SCENARIO: "scenarios",
            ColorCategory.MODEL_YEAR: "model_years",
            ColorCategory.SECTOR: "sectors",
            ColorCategory.END_USE: "end_uses",
        }
        group_name = _cat_to_group.get(resolved)
        if group_name:
            d = groups[group_name]
            return {group_name: _fmt(d)} if d else {}

        return {}

    def to_dict(self) -> dict[str, Any]:
        """Serializes the internal palette to a structured dictionary.

        Includes a ``"themes"`` key when the palette uses custom color
        cycles (a "full" palette).  Minimal palettes omit it.

        Returns
        -------
        dict[str, Any]
            A dictionary with 'scenarios', 'model_years', 'sectors', and
            'end_uses' keys, each mapping labels to hex color strings.
            Optionally includes 'themes' for full palettes.
        """
        result: dict[str, Any] = {
            "scenarios": self.scenarios.copy(),
            "model_years": self.model_years.copy(),
            "sectors": self.sectors.copy(),
            "end_uses": self.end_uses.copy(),
        }
        if self.has_custom_themes:
            result["themes"] = {
                "scenarios": list(self.scenario_theme),
                "model_years": list(self.model_year_theme),
                "sectors": list(self.metric_theme),
                "end_uses": list(self.metric_theme),
            }
        return result

    def to_dict_legacy(self) -> dict[str, dict[str, str]]:
        """Serializes the palette using the legacy 3-key format.

        Sectors and end-uses are merged under a single ``"metrics"`` key.
        Prefer :meth:`to_dict` for new code.
        """
        return {
            "scenarios": self.scenarios.copy(),
            "model_years": self.model_years.copy(),
            "metrics": {**self.sectors, **self.end_uses},
        }

    def to_flat_dict(self) -> dict[str, str]:
        """Serializes the internal palette to a flat dictionary (all categories combined).

        Returns
        -------
        dict[str, str]
            A flat mapping of all labels to corresponding hex color strings.
        """
        result = {}
        result.update(self.scenarios)
        result.update(self.model_years)
        result.update(self.sectors)
        result.update(self.end_uses)
        return result

    def move_item_up(self, items: MutableSequence[dict[str, Any]], index: int) -> bool:
        """Move an item up in the list (swap with previous item).

        Parameters
        ----------
        items : MutableSequence[dict[str, Any]]
            The list of palette items to reorder
        index : int
            The index of the item to move up

        Returns
        -------
        bool
            True if the item was moved, False if it was already at the top
        """
        if index > 0:
            items[index - 1], items[index] = items[index], items[index - 1]
            # Update order values
            items[index - 1]["order"], items[index]["order"] = (
                items[index]["order"],
                items[index - 1]["order"],
            )
            return True
        return False

    def move_item_down(self, items: MutableSequence[dict[str, Any]], index: int) -> bool:
        """Move an item down in the list (swap with next item).

        Parameters
        ----------
        items : MutableSequence[dict[str, Any]]
            The list of palette items to reorder
        index : int
            The index of the item to move down

        Returns
        -------
        bool
            True if the item was moved, False if it was already at the bottom
        """
        if index < len(items) - 1:
            items[index], items[index + 1] = items[index + 1], items[index]
            # Update order values
            items[index]["order"], items[index + 1]["order"] = (
                items[index + 1]["order"],
                items[index]["order"],
            )
            return True
        return False

    @staticmethod
    def palette_to_grouped_items(
        palette: dict[str, dict[str, str]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Convert a structured palette into a dict of lists of items.

        Parameters
        ----------
        palette : dict[str, dict[str, str]]
            Structured palette with 'scenarios', 'model_years', 'sectors',
            and 'end_uses' categories (also accepts legacy 'metrics' key).

        Returns
        -------
        dict[str, list[dict[str, Any]]]
            Dictionary mapping category names to lists of PaletteItems with order
        """
        result: dict[str, list[dict[str, Any]]] = {}

        # Map internal names to display names
        category_display_names = {
            "scenarios": "Scenarios",
            "model_years": "Model Years",
            "sectors": "Sectors",
            "end_uses": "End Uses",
            "metrics": "Sectors",  # legacy compat
        }

        for category_name in ["scenarios", "model_years", "sectors", "end_uses", "metrics"]:
            category_dict = palette.get(category_name, {})
            if category_dict:
                items: list[dict[str, Any]] = []
                for order, (label, color) in enumerate(category_dict.items()):
                    items.append({"label": label, "color": color, "order": order})
                display_name = category_display_names.get(category_name, category_name)
                if display_name in result:
                    # Append to existing group (e.g. legacy metrics merging into Sectors)
                    offset = len(result[display_name])
                    for item in items:
                        item["order"] += offset
                    result[display_name].extend(items)
                else:
                    result[display_name] = items

        return result

    @staticmethod
    def grouped_items_to_palette(
        grouped_items: Mapping[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, str]]:
        """Convert a structured dict of lists of items back to a palette.

        Parameters
        ----------
        grouped_items : Mapping[str, list[dict[str, Any]]]
            Dictionary mapping group names to lists of PaletteItems

        Returns
        -------
        dict[str, dict[str, str]]
            Structured palette with 'scenarios', 'model_years', 'sectors',
            and 'end_uses' categories.
        """
        # Map display names back to internal names
        display_to_category = {
            "Scenarios": "scenarios",
            "Model Years": "model_years",
            "Sectors": "sectors",
            "End Uses": "end_uses",
        }

        palette: dict[str, dict[str, str]] = {
            "scenarios": {},
            "model_years": {},
            "sectors": {},
            "end_uses": {},
        }

        for display_name, items in grouped_items.items():
            category_name = display_to_category.get(display_name)
            if category_name:
                # Sort by order to maintain user-defined ordering
                sorted_items = sorted(items, key=lambda x: x["order"])
                for item in sorted_items:
                    palette[category_name][item["label"]] = item["color"]

        return palette
