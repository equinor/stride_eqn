"""Test that user-edited colors survive the save-as-user-palette round-trip.

Reproduces the bug where a user changes a color in the settings UI,
clicks "Save As User Palette", enters a name, clicks again, and the
custom color vanishes both from the display and (seemingly) from disk.

Root cause: ``set_ui_theme()`` unconditionally overwrites all model-year
colors with freshly sampled iridescent values.  The file on disk IS
correct, but every subsequent load goes through ``create_fresh_color_manager``
→ ``set_ui_theme`` → all model-year edits are lost.
"""

from __future__ import annotations

import json
from itertools import cycle
from unittest.mock import patch

import pytest

from stride.ui.color_manager import ColorManager
from stride.ui.palette import ColorPalette
from stride.ui.settings.callbacks import register_settings_callbacks
from stride.ui.settings.layout import (
    clear_temp_color_edits,
    set_temp_color_edit,
)


# ── helpers ──────────────────────────────────────────────────────────────
def _make_palette() -> ColorPalette:
    """Build a small palette with all four categories populated."""
    data = {
        "scenarios": {"reference": "#4477AA", "high_growth": "#CCBB44"},
        "model_years": {"2025": "#9B8AC4", "2030": "#9A709E", "2035": "#906388"},
        "sectors": {"residential": "#CC6677", "commercial": "#999933"},
        "end_uses": {"heating": "#5289C7", "cooling": "#117733"},
    }
    return ColorPalette.from_dict(data)


CUSTOM_HEX = "#FF0000"  # unmistakable custom color

# Parametrize tuples: (composite_key_category, dict_key, label)
_ALL_CATEGORIES = [
    ("scenarios", "scenarios", "reference"),
    ("model_years", "model_years", "2030"),
    ("sector", "sectors", "residential"),
    ("end_use", "end_uses", "heating"),
]


def _palette_dict(palette: ColorPalette, dict_key: str) -> dict[str, str]:
    """Return the palette attribute dict for a to_dict() key name."""
    return {
        "scenarios": palette.scenarios,
        "model_years": palette.model_years,
        "sectors": palette.sectors,
        "end_uses": palette.end_uses,
    }[dict_key]


# ── tests ────────────────────────────────────────────────────────────────


class TestSetUiThemePreservesCustomColors:
    """Unit tests for ``set_ui_theme`` preserving user-customised colours.

    These isolate the ``set_ui_theme`` method directly, without involving
    callbacks or disk I/O, so a regression in ``set_ui_theme`` is
    immediately pinpointed.
    """

    @pytest.mark.parametrize("cat, dict_key, label", _ALL_CATEGORIES)
    @pytest.mark.parametrize("theme", ["light", "dark"])
    def test_edit_survives_set_ui_theme(self, cat, dict_key, label, theme):
        """Custom colors must survive ``set_ui_theme``."""
        palette = _make_palette()
        palette.update(label, CUSTOM_HEX, category=cat)

        palette.set_ui_theme(theme)

        assert _palette_dict(palette, dict_key)[label] == CUSTOM_HEX, (
            f"set_ui_theme('{theme}') clobbered the custom {dict_key} " f"color for '{label}'"
        )


# ── helper: create a real ColorManager bypassing the singleton ───────────
def _make_color_manager(palette: ColorPalette) -> ColorManager:
    """Build a standalone ``ColorManager`` (no singleton side-effects)."""
    cm = object.__new__(ColorManager)
    cm._initialized = False
    cm._scenario_colors = {}
    ColorManager.__init__(cm, palette)
    cm.initialize_colors(
        scenarios=list(palette.scenarios.keys()),
        sectors=list(palette.sectors.keys()),
        end_uses=list(palette.end_uses.keys()),
    )
    return cm


def _capture_settings_callbacks(get_dh, get_cm, on_change):
    """Call ``register_settings_callbacks`` with a mocked ``@callback``.

    Returns a dict mapping function name → the original (unwrapped)
    callback function.  Closure variables (``get_color_manager_func``,
    ``on_palette_change_func``, etc.) are bound to the arguments passed
    here.
    """
    captured: dict[str, object] = {}

    def fake_callback(*_args, **_kwargs):
        """Replacement for ``dash.callback`` – just record the function."""

        def decorator(func):
            captured[func.__name__] = func
            return func

        return decorator

    with patch("stride.ui.settings.callbacks.callback", fake_callback):
        register_settings_callbacks(get_dh, get_cm, on_change)

    return captured


class TestSaveCallbackDirectly:
    """Invoke the *real* ``save_to_new_palette`` callback via MagicMock.

    By mocking ``dash.callback`` as a no-op decorator we can capture the
    nested function that ``register_settings_callbacks`` creates and call
    it directly with controlled arguments.
    """

    def setup_method(self):
        clear_temp_color_edits()

    def teardown_method(self):
        clear_temp_color_edits()

    # -- file-on-disk correctness -----------------------------------------

    def test_callback_writes_custom_color_to_disk(self, tmp_path, monkeypatch):
        """``save_to_new_palette`` must persist the edited color to JSON."""
        palette_dir = tmp_path / "palettes"
        palette_dir.mkdir()
        monkeypatch.setattr("stride.ui.tui.get_user_palette_dir", lambda: palette_dir)

        palette = _make_palette()
        cm = _make_color_manager(palette)

        on_change_calls: list[tuple] = []
        cbs = _capture_settings_callbacks(
            lambda: None,
            lambda: cm,
            lambda p, t, n: on_change_calls.append((p, t, n)),
        )

        set_temp_color_edit("model_years:2030", CUSTOM_HEX)
        cbs["save_to_new_palette"](1, "my_palette")

        # The JSON on disk must contain the custom color.
        raw = json.loads((palette_dir / "my_palette.json").read_text())
        assert raw["palette"]["model_years"]["2030"] == CUSTOM_HEX

    def test_callback_passes_custom_color_to_on_palette_change(self, tmp_path, monkeypatch):
        """The palette handed to ``on_palette_change_func`` must carry the edit."""
        palette_dir = tmp_path / "palettes"
        palette_dir.mkdir()
        monkeypatch.setattr("stride.ui.tui.get_user_palette_dir", lambda: palette_dir)

        palette = _make_palette()
        cm = _make_color_manager(palette)

        received_palettes: list[ColorPalette] = []
        cbs = _capture_settings_callbacks(
            lambda: None,
            lambda: cm,
            lambda p, _t, _n: received_palettes.append(p.copy()),
        )

        set_temp_color_edit("model_years:2030", CUSTOM_HEX)
        cbs["save_to_new_palette"](1, "my_palette")

        assert len(received_palettes) == 1
        assert received_palettes[0].model_years["2030"] == CUSTOM_HEX

    # -- the real bug: set_ui_theme inside on_palette_change clobbers ----

    @pytest.mark.parametrize("theme", ["light", "dark"])
    def test_callback_color_survives_on_palette_change_chain(self, tmp_path, monkeypatch, theme):
        """Reproduce the full bug: save → on_palette_change → set_ui_theme.

        ``on_palette_change`` (in app.py) calls
        ``create_fresh_color_manager`` which calls ``set_ui_theme``.
        The custom model-year color must survive that call.
        """
        palette_dir = tmp_path / "palettes"
        palette_dir.mkdir()
        monkeypatch.setattr("stride.ui.tui.get_user_palette_dir", lambda: palette_dir)

        palette = _make_palette()
        cm = _make_color_manager(palette)

        # Simulate what the real on_palette_change → create_fresh_color_manager does.
        result_palettes: list[ColorPalette] = []

        def realistic_on_palette_change(p, _ptype, _pname):
            p_copy = p.copy()
            p_copy._scenario_iterator = cycle(p_copy.scenario_theme)
            p_copy.set_ui_theme(theme)
            result_palettes.append(p_copy)

        cbs = _capture_settings_callbacks(
            lambda: None,
            lambda: cm,
            realistic_on_palette_change,
        )

        set_temp_color_edit("model_years:2030", CUSTOM_HEX)
        cbs["save_to_new_palette"](1, "my_palette")

        assert len(result_palettes) == 1
        assert result_palettes[0].model_years["2030"] == CUSTOM_HEX, (
            f"set_ui_theme('{theme}') inside on_palette_change clobbered "
            "the custom model-year color that was just saved"
        )

    @pytest.mark.parametrize("cat, dict_key, label", _ALL_CATEGORIES)
    def test_callback_all_categories_survive_chain(
        self, tmp_path, monkeypatch, cat, dict_key, label
    ):
        """Every category's custom color must survive the full callback chain."""
        palette_dir = tmp_path / "palettes"
        palette_dir.mkdir()
        monkeypatch.setattr("stride.ui.tui.get_user_palette_dir", lambda: palette_dir)

        palette = _make_palette()
        cm = _make_color_manager(palette)

        result_palettes: list[ColorPalette] = []

        def realistic_on_palette_change(p, _ptype, _pname):
            p_copy = p.copy()
            p_copy._scenario_iterator = cycle(p_copy.scenario_theme)
            p_copy.set_ui_theme("light")
            result_palettes.append(p_copy)

        cbs = _capture_settings_callbacks(
            lambda: None,
            lambda: cm,
            realistic_on_palette_change,
        )

        set_temp_color_edit(f"{cat}:{label}", CUSTOM_HEX)
        cbs["save_to_new_palette"](1, "my_palette")

        assert len(result_palettes) == 1
        assert _palette_dict(result_palettes[0], dict_key)[label] == CUSTOM_HEX, (
            f"Custom {dict_key} color for '{label}' was clobbered after "
            "save_to_new_palette → on_palette_change → set_ui_theme"
        )
