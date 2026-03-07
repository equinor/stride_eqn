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
    ColorCategory,
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
        palette.update("metric_a", category=ColorCategory.SECTOR)
        palette.update("metric_b", category=ColorCategory.SECTOR)

        palette.set_ui_theme("dark")

        assert palette._ui_theme == "dark"
        assert palette.metric_theme == list(TOL_METRICS_DARK)
        # Sectors should be reassigned with dark-mode colors
        assert palette.sectors["metric_a"] == TOL_METRICS_DARK[0]
        assert palette.sectors["metric_b"] == TOL_METRICS_DARK[1]

    def test_switch_back_to_light(self):
        palette = ColorPalette()
        palette.update("metric_a", category=ColorCategory.SECTOR)
        palette.set_ui_theme("dark")
        palette.set_ui_theme("light")
        assert palette._ui_theme == "light"
        assert palette.sectors["metric_a"] == TOL_METRICS_LIGHT[0]

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

    def test_sector_colors_from_tol_metrics_light(self):
        palette = ColorPalette()
        palette.update("test_metric", category=ColorCategory.SECTOR)
        assert palette.sectors["test_metric"] == TOL_METRICS_LIGHT[0]

    def test_model_year_colors_from_tol_iridescent(self):
        palette = ColorPalette()
        palette.update("2020", category="model_years")
        assert palette.model_years["2020"] == TOL_IRIDESCENT[0]


class TestIndependentBreakdownColors:
    """Verify that sectors and end-uses get independent color sequences.

    Both should start from position 0 in the metric theme, regardless of
    which group was registered first or how many items the other group has.
    """

    def test_sectors_and_end_uses_start_from_same_first_color(self):
        """Sectors and end-uses should both begin at metric_theme[0]."""
        palette = ColorPalette()

        # Register several sectors first
        palette.update("residential", category=ColorCategory.SECTOR)
        palette.update("commercial", category=ColorCategory.SECTOR)
        palette.update("industrial", category=ColorCategory.SECTOR)

        # Now register end-uses — these should NOT continue after industrial
        palette.update("heating", category=ColorCategory.END_USE)

        assert palette.sectors["residential"] == TOL_METRICS_LIGHT[0]
        assert palette.sectors["commercial"] == TOL_METRICS_LIGHT[1]
        assert palette.sectors["industrial"] == TOL_METRICS_LIGHT[2]
        # Key assertion: heating starts at [0], not [3]
        assert palette.end_uses["heating"] == TOL_METRICS_LIGHT[0]

    def test_end_uses_registered_first_then_sectors(self):
        """Order shouldn't matter — reversing registration order works too."""
        palette = ColorPalette()

        palette.update("heating", category=ColorCategory.END_USE)
        palette.update("cooling", category=ColorCategory.END_USE)

        palette.update("residential", category=ColorCategory.SECTOR)

        # End-uses got [0] and [1]; sectors restart at [0]
        assert palette.end_uses["heating"] == TOL_METRICS_LIGHT[0]
        assert palette.end_uses["cooling"] == TOL_METRICS_LIGHT[1]
        assert palette.sectors["residential"] == TOL_METRICS_LIGHT[0]

    def test_get_also_uses_independent_iterators(self):
        """palette.get() should use the same independent iterators as update()."""
        palette = ColorPalette()

        # Use get() to auto-assign colors — pass ColorCategory directly
        s1 = palette.get("sector_a", category=ColorCategory.SECTOR)
        s2 = palette.get("sector_b", category=ColorCategory.SECTOR)
        e1 = palette.get("end_use_a", category=ColorCategory.END_USE)
        e2 = palette.get("end_use_b", category=ColorCategory.END_USE)

        assert s1 == TOL_METRICS_LIGHT[0]
        assert s2 == TOL_METRICS_LIGHT[1]
        # End-uses restart at [0]
        assert e1 == TOL_METRICS_LIGHT[0]
        assert e2 == TOL_METRICS_LIGHT[1]

    def test_interleaved_registration_stays_independent(self):
        """Interleaving sector and end-use registrations keeps sequences separate."""
        palette = ColorPalette()

        palette.update("sector_1", category=ColorCategory.SECTOR)
        palette.update("end_use_1", category=ColorCategory.END_USE)
        palette.update("sector_2", category=ColorCategory.SECTOR)
        palette.update("end_use_2", category=ColorCategory.END_USE)

        assert palette.sectors["sector_1"] == TOL_METRICS_LIGHT[0]
        assert palette.sectors["sector_2"] == TOL_METRICS_LIGHT[1]
        assert palette.end_uses["end_use_1"] == TOL_METRICS_LIGHT[0]
        assert palette.end_uses["end_use_2"] == TOL_METRICS_LIGHT[1]

    def test_independent_sequences_after_theme_switch(self):
        """After switching to dark mode, sequences should still be independent."""
        palette = ColorPalette()

        palette.update("sector_a", category=ColorCategory.SECTOR)
        palette.update("end_use_a", category=ColorCategory.END_USE)

        palette.set_ui_theme("dark")

        # After theme switch, both should be reassigned from dark theme position 0
        assert palette.sectors["sector_a"] == TOL_METRICS_DARK[0]
        assert palette.end_uses["end_use_a"] == TOL_METRICS_DARK[0]
