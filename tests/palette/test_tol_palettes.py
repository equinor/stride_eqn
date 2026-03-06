"""Tests for Paul Tol color-blind-safe palette integration.

Validates that the Tol palette constants, sample_iridescent interpolation,
and set_ui_theme method work correctly.
"""

import pytest

from stride.ui.palette import (
    TOL_BRIGHT,
    TOL_IRIDESCENT,
    TOL_METRICS_DARK,
    TOL_METRICS_LIGHT,
    ColorPalette,
    sample_iridescent,
)


class TestTolPaletteConstants:
    """Verify Tol palette constants are well-formed."""

    @pytest.mark.parametrize(
        "palette,expected_len",
        [
            (TOL_BRIGHT, 7),
            (TOL_METRICS_LIGHT, 12),
            (TOL_METRICS_DARK, 16),
            (TOL_IRIDESCENT, 23),
        ],
    )
    def test_palette_lengths(self, palette, expected_len):
        assert len(palette) == expected_len

    @pytest.mark.parametrize(
        "palette", [TOL_BRIGHT, TOL_METRICS_LIGHT, TOL_METRICS_DARK, TOL_IRIDESCENT]
    )
    def test_all_hex_format(self, palette):
        for color in palette:
            assert color.startswith("#"), f"{color} does not start with #"
            assert len(color) == 7, f"{color} is not 7 characters"

    def test_bright_no_duplicates(self):
        assert len(set(TOL_BRIGHT)) == len(TOL_BRIGHT)

    def test_metrics_light_no_duplicates(self):
        assert len(set(TOL_METRICS_LIGHT)) == len(TOL_METRICS_LIGHT)

    def test_metrics_dark_no_duplicates(self):
        assert len(set(TOL_METRICS_DARK)) == len(TOL_METRICS_DARK)


class TestSampleIridescent:
    """Test the sample_iridescent interpolation function."""

    def test_zero_colors(self):
        assert sample_iridescent(0) == []

    def test_single_color(self):
        result = sample_iridescent(1, theme="light")
        assert len(result) == 1
        assert result[0].startswith("#")

    def test_light_mode_range(self):
        """Light mode should use idx 16–22 (7 native colors)."""
        colors = sample_iridescent(7, theme="light")
        assert len(colors) == 7
        # First and last should match the Iridescent endpoints for light
        assert colors[0] == TOL_IRIDESCENT[16]
        assert colors[-1] == TOL_IRIDESCENT[22]

    def test_dark_mode_range(self):
        """Dark mode should use idx 0–19 (20 native colors)."""
        colors = sample_iridescent(20, theme="dark")
        assert len(colors) == 20
        assert colors[0] == TOL_IRIDESCENT[0]
        assert colors[-1] == TOL_IRIDESCENT[19]

    def test_interpolation_produces_unique_colors(self):
        """When requesting more colors than native, interpolation should still produce unique values."""
        colors = sample_iridescent(10, theme="light")
        assert len(colors) == 10
        # All should be valid hex
        for c in colors:
            assert c.startswith("#") and len(c) == 7
        # Most should be unique (some edge cases could overlap)
        assert len(set(colors)) >= 8

    def test_two_colors(self):
        """Requesting exactly 2 should give endpoints."""
        colors = sample_iridescent(2, theme="dark")
        assert len(colors) == 2
        assert colors[0] == TOL_IRIDESCENT[0]
        assert colors[-1] == TOL_IRIDESCENT[19]


class TestSetUiTheme:
    """Test the set_ui_theme method on ColorPalette."""

    def test_default_is_light(self):
        palette = ColorPalette()
        assert palette._ui_theme == "light"
        assert palette.metric_theme == list(TOL_METRICS_LIGHT)

    def test_switch_to_dark(self):
        palette = ColorPalette()
        palette.update("metric_a", category="metrics")
        palette.update("metric_b", category="metrics")

        palette.set_ui_theme("dark")

        assert palette._ui_theme == "dark"
        assert palette.metric_theme == list(TOL_METRICS_DARK)
        # Metrics should be reassigned with dark-mode colors
        assert palette.metrics["metric_a"] == TOL_METRICS_DARK[0]
        assert palette.metrics["metric_b"] == TOL_METRICS_DARK[1]

    def test_switch_back_to_light(self):
        palette = ColorPalette()
        palette.update("metric_a", category="metrics")
        palette.set_ui_theme("dark")
        palette.set_ui_theme("light")
        assert palette._ui_theme == "light"
        assert palette.metrics["metric_a"] == TOL_METRICS_LIGHT[0]

    def test_model_years_resampled(self):
        palette = ColorPalette()
        palette.update("2020", category="model_years")
        palette.update("2030", category="model_years")
        palette.update("2040", category="model_years")

        palette.set_ui_theme("dark")
        dark_colors = list(palette.model_years.values())

        palette.set_ui_theme("light")
        light_colors = list(palette.model_years.values())

        # Dark and light should use different Iridescent ranges
        assert dark_colors != light_colors

    def test_invalid_theme_raises(self):
        palette = ColorPalette()
        with pytest.raises(ValueError, match="Invalid UI theme"):
            palette.set_ui_theme("midnight")

    def test_scenarios_unchanged_by_theme(self):
        """Scenarios use Tol Bright which is theme-independent."""
        palette = ColorPalette()
        palette.update("scen_a", category="scenarios")
        color_before = palette.scenarios["scen_a"]

        palette.set_ui_theme("dark")
        color_after = palette.scenarios["scen_a"]

        assert color_before == color_after


class TestDefaultPaletteColors:
    """Test that new ColorPalette uses Tol colors by default."""

    def test_scenario_colors_from_tol_bright(self):
        palette = ColorPalette()
        palette.update("test_scenario", category="scenarios")
        assert palette.scenarios["test_scenario"] == TOL_BRIGHT[0]

    def test_metric_colors_from_tol_metrics_light(self):
        palette = ColorPalette()
        palette.update("test_metric", category="metrics")
        assert palette.metrics["test_metric"] == TOL_METRICS_LIGHT[0]

    def test_model_year_colors_from_tol_iridescent(self):
        palette = ColorPalette()
        palette.update("2020", category="model_years")
        assert palette.model_years["2020"] == TOL_IRIDESCENT[0]
