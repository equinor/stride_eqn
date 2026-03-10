"""Tests for the ColorPalette class."""

from typing import Any

import pytest

from stride.ui.palette import ColorCategory, ColorPalette


class TestColorPaletteInitialization:
    """Test ColorPalette initialization."""

    def test_empty_initialization(self) -> None:
        """Test creating an empty palette."""
        palette = ColorPalette()
        assert isinstance(palette.palette, dict)
        assert len(palette.palette) == 0

    def test_initialization_with_dict(self) -> None:
        """Test creating a palette with initial colors."""
        initial_colors = {
            "residential": "#FF5733",
            "commercial": "#3498DB",
        }
        palette = ColorPalette.from_dict(initial_colors)
        assert len(palette.palette) == 2
        assert palette.palette["residential"] == "#FF5733"
        assert palette.palette["commercial"] == "#3498DB"

    def test_initialization_with_invalid_colors(self) -> None:
        """Test that invalid colors are replaced during initialization."""
        initial_colors = {
            "residential": "not_a_color",
            "commercial": "#3498DB",
        }
        palette = ColorPalette.from_dict(initial_colors)
        assert len(palette.palette) == 2
        assert palette.palette["commercial"] == "#3498DB"
        # Invalid color should be replaced with a generated one
        assert palette.palette["residential"] != "not_a_color"


class TestColorPaletteUpdate:
    """Test ColorPalette update method."""

    def test_update_with_valid_hex(self) -> None:
        """Test updating with a valid hex color."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        assert palette.palette["residential"] == "#FF5733"

    def test_update_with_valid_hex_alpha(self) -> None:
        """Test updating with a valid hex color with alpha."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733CC")
        assert palette.palette["residential"] == "#FF5733CC"

    def test_update_with_none(self) -> None:
        """Test that None generates a new color."""
        palette = ColorPalette()
        palette.update("residential", None)
        assert "residential" in palette.palette
        assert palette.palette["residential"] is not None

    def test_update_with_invalid_string(self) -> None:
        """Test that invalid color strings generate new colors."""
        palette = ColorPalette()
        palette.update("residential", "not_a_hex")
        assert "residential" in palette.palette
        assert palette.palette["residential"] != "not_a_hex"

    def test_update_non_string_key_raises_error(self) -> None:
        """Test that non-string keys raise TypeError."""
        palette = ColorPalette()
        with pytest.raises(TypeError, match="Key must be a string"):
            palette.update(123, "#FF5733")  # type: ignore[arg-type]

    def test_update_overwrites_existing(self) -> None:
        """Test that update overwrites existing colors."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        palette.update("residential", "#3498DB")
        assert palette.palette["residential"] == "#3498DB"


class TestColorPaletteGet:
    """Test ColorPalette get method."""

    def test_get_existing_color(self) -> None:
        """Test getting an existing color."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        color = palette.get("residential")
        assert color == "#FF5733"

    def test_get_nonexistent_generates_color(self) -> None:
        """Test that getting a nonexistent key generates a color."""
        palette = ColorPalette()
        color = palette.get("new_key")
        assert "new_key" in palette.palette
        assert color is not None
        assert len(color) > 0

    def test_get_multiple_times_returns_same_color(self) -> None:
        """Test that getting the same key multiple times returns the same color."""
        palette = ColorPalette()
        color1 = palette.get("residential")
        color2 = palette.get("residential")
        assert color1 == color2


class TestColorPalettePop:
    """Test ColorPalette pop method."""

    def test_pop_existing_key(self) -> None:
        """Test popping an existing key."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        color = palette.pop("residential")
        assert color == "#FF5733"
        assert "residential" not in palette.palette

    def test_pop_nonexistent_key_raises_error(self) -> None:
        """Test that popping a nonexistent key raises KeyError."""
        palette = ColorPalette()
        with pytest.raises(KeyError, match="unable to remove key"):
            palette.pop("nonexistent")


class TestColorPaletteFromDict:
    """Test ColorPalette.from_dict class method."""

    def test_from_dict_with_valid_colors(self) -> None:
        """Test creating palette from dict with valid colors."""
        colors = {
            "residential": "#FF5733",
            "commercial": "#3498DB",
            "industrial": "#2ECC71",
        }
        palette = ColorPalette.from_dict(colors)
        assert len(palette.palette) == 3
        assert palette.palette["residential"] == "#FF5733"
        assert palette.palette["commercial"] == "#3498DB"
        assert palette.palette["industrial"] == "#2ECC71"

    def test_from_dict_with_invalid_colors(self) -> None:
        """Test that invalid colors are replaced when loading from dict."""
        colors = {
            "residential": "not_a_color",
            "commercial": "#3498DB",
            "industrial": "also_not_a_color",
        }
        palette = ColorPalette.from_dict(colors)
        assert len(palette.palette) == 3
        assert palette.palette["commercial"] == "#3498DB"
        # Invalid colors should be replaced
        assert palette.palette["residential"] != "not_a_color"
        assert palette.palette["industrial"] != "also_not_a_color"

    def test_from_dict_empty(self) -> None:
        """Test creating palette from empty dict."""
        palette = ColorPalette.from_dict({})
        assert len(palette.palette) == 0


class TestColorPaletteToDict:
    """Test ColorPalette.to_dict method."""

    def test_to_dict_empty(self) -> None:
        """Test converting empty palette to dict."""
        palette = ColorPalette()
        result = palette.to_dict()
        assert isinstance(result, dict)
        # Structured format has 4 categories
        assert len(result) == 4
        assert "scenarios" in result
        assert "model_years" in result
        assert "sectors" in result
        assert "end_uses" in result
        assert len(result["scenarios"]) == 0
        assert len(result["model_years"]) == 0
        assert len(result["sectors"]) == 0
        assert len(result["end_uses"]) == 0

    def test_to_dict_with_colors(self) -> None:
        """Test converting palette with colors to dict."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733", category=ColorCategory.SECTOR)
        palette.update("commercial", "#3498DB", category=ColorCategory.SECTOR)
        result = palette.to_dict()
        assert "sectors" in result
        assert result["sectors"]["residential"] == "#FF5733"
        assert result["sectors"]["commercial"] == "#3498DB"

    def test_to_dict_returns_copy(self) -> None:
        """Test that to_dict returns a copy, not the original dict."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733", category=ColorCategory.SECTOR)
        result = palette.to_dict()
        result["sectors"]["new_key"] = "#000000"
        assert "new_key" not in palette.palette


class TestColorPaletteRoundTrip:
    """Test round-trip serialization/deserialization."""

    def test_round_trip_preserves_colors(self) -> None:
        """Test that to_dict and from_dict preserve colors."""
        original = ColorPalette()
        original.update("residential", "#FF5733")
        original.update("commercial", "#3498DB")
        original.update("industrial", "#2ECC71")

        # Serialize and deserialize
        dict_repr = original.to_dict()
        restored = ColorPalette.from_dict(dict_repr)

        # Check all colors are preserved
        assert len(restored.palette) == len(original.palette)
        for key in original.palette:
            assert restored.palette[key] == original.palette[key]


class TestColorPaletteColorGeneration:
    """Test color generation behavior."""

    def test_auto_generation_creates_unique_colors(self) -> None:
        """Test that auto-generated colors are different."""
        palette = ColorPalette()
        color1 = palette.get("key1")
        color2 = palette.get("key2")
        color3 = palette.get("key3")

        # Colors should be different (most of the time)
        # Note: There's a small chance they could be the same if the cycle repeats
        colors = [color1, color2, color3]
        assert len(set(colors)) >= 2  # At least 2 should be different

    def test_multiple_palettes_independent(self) -> None:
        """Test that multiple palette instances are independent."""
        palette1 = ColorPalette()
        palette2 = ColorPalette()

        palette1.update("residential", "#FF5733")
        palette2.update("residential", "#3498DB")

        assert palette1.get("residential") == "#FF5733"
        assert palette2.get("residential") == "#3498DB"


class TestColorPaletteHexValidation:
    """Test hex color validation."""

    def test_valid_6_digit_hex(self) -> None:
        """Test that 6-digit hex colors are accepted."""
        palette = ColorPalette()
        palette.update("test", "#FF5733")
        assert palette.palette["test"] == "#FF5733"

    def test_valid_8_digit_hex(self) -> None:
        """Test that 8-digit hex colors (with alpha) are accepted."""
        palette = ColorPalette()
        palette.update("test", "#FF5733CC")
        assert palette.palette["test"] == "#FF5733CC"

    def test_lowercase_hex(self) -> None:
        """Test that lowercase hex colors are accepted."""
        palette = ColorPalette()
        palette.update("test", "#ff5733")
        assert palette.palette["test"] == "#ff5733"

    def test_mixed_case_hex(self) -> None:
        """Test that mixed case hex colors are accepted."""
        palette = ColorPalette()
        palette.update("test", "#Ff5733")
        assert palette.palette["test"] == "#Ff5733"

    def test_invalid_short_hex(self) -> None:
        """Test that short hex colors are rejected."""
        palette = ColorPalette()
        palette.update("test", "#F57")
        # Should be replaced with auto-generated color
        assert palette.palette["test"] != "#F57"

    def test_invalid_no_hash(self) -> None:
        """Test that colors without # are rejected."""
        palette = ColorPalette()
        palette.update("test", "FF5733")
        assert palette.palette["test"] != "FF5733"

    def test_invalid_non_hex_chars(self) -> None:
        """Test that non-hex characters are rejected."""
        palette = ColorPalette()
        palette.update("test", "#GGGGGG")
        assert palette.palette["test"] != "#GGGGGG"


class TestColorPaletteReordering:
    """Test ColorPalette reordering methods."""

    def test_move_item_up_success(self) -> None:
        """Test moving an item up in the list."""
        palette = ColorPalette()
        items: list[dict[str, Any]] = [
            {"label": "item1", "color": "#FF0000", "order": 0},
            {"label": "item2", "color": "#00FF00", "order": 1},
            {"label": "item3", "color": "#0000FF", "order": 2},
        ]

        result = palette.move_item_up(items, 1)
        assert result is True
        assert items[0]["label"] == "item2"
        assert items[1]["label"] == "item1"
        # After swap, item2 (now at index 0) should have order 0
        # and item1 (now at index 1) should have order 1
        assert items[0]["order"] == 0
        assert items[1]["order"] == 1

    def test_move_item_up_at_top(self) -> None:
        """Test that moving the top item up returns False."""
        palette = ColorPalette()
        items: list[dict[str, Any]] = [
            {"label": "item1", "color": "#FF0000", "order": 0},
            {"label": "item2", "color": "#00FF00", "order": 1},
        ]

        result = palette.move_item_up(items, 0)
        assert result is False
        assert items[0]["label"] == "item1"
        assert items[1]["label"] == "item2"

    def test_move_item_down_success(self) -> None:
        """Test moving an item down in the list."""
        palette = ColorPalette()
        items: list[dict[str, Any]] = [
            {"label": "item1", "color": "#FF0000", "order": 0},
            {"label": "item2", "color": "#00FF00", "order": 1},
            {"label": "item3", "color": "#0000FF", "order": 2},
        ]

        result = palette.move_item_down(items, 1)
        assert result is True
        assert items[1]["label"] == "item3"
        assert items[2]["label"] == "item2"
        # After swap, item3 (now at index 1) should have order 1
        # and item2 (now at index 2) should have order 2
        assert items[1]["order"] == 1
        assert items[2]["order"] == 2

    def test_move_item_down_at_bottom(self) -> None:
        """Test that moving the bottom item down returns False."""
        palette = ColorPalette()
        items: list[dict[str, Any]] = [
            {"label": "item1", "color": "#FF0000", "order": 0},
            {"label": "item2", "color": "#00FF00", "order": 1},
        ]

        result = palette.move_item_down(items, 1)
        assert result is False
        assert items[0]["label"] == "item1"
        assert items[1]["label"] == "item2"

    def test_move_multiple_times(self) -> None:
        """Test moving items multiple times."""
        palette = ColorPalette()
        items: list[dict[str, Any]] = [
            {"label": "item1", "color": "#FF0000", "order": 0},
            {"label": "item2", "color": "#00FF00", "order": 1},
            {"label": "item3", "color": "#0000FF", "order": 2},
        ]

        # Move item3 up twice to reach the top
        palette.move_item_up(items, 2)
        assert items[1]["label"] == "item3"
        palette.move_item_up(items, 1)
        assert items[0]["label"] == "item3"


class TestColorPaletteGroupedItems:
    """Test ColorPalette grouped items conversion methods."""

    def test_palette_to_grouped_items(self) -> None:
        """Test converting palette to grouped items format."""
        palette = {
            "scenarios": {"baseline": "#0000FF"},
            "model_years": {},
            "sectors": {"heating": "#FF0000", "cooling": "#00FF00"},
            "end_uses": {},
        }

        result = ColorPalette.palette_to_grouped_items(palette)

        assert "Sectors" in result
        assert "Scenarios" in result
        assert len(result["Sectors"]) == 2
        assert len(result["Scenarios"]) == 1
        assert result["Sectors"][0]["label"] == "heating"
        assert result["Sectors"][0]["color"] == "#FF0000"
        assert result["Sectors"][0]["order"] == 0
        assert result["Sectors"][1]["label"] == "cooling"
        assert result["Sectors"][1]["order"] == 1

    def test_grouped_items_to_palette(self) -> None:
        """Test converting grouped items back to structured palette."""
        grouped_items: dict[str, list[dict[str, Any]]] = {
            "Sectors": [
                {"label": "heating", "color": "#FF0000", "order": 0},
                {"label": "cooling", "color": "#00FF00", "order": 1},
            ],
            "Scenarios": [
                {"label": "baseline", "color": "#0000FF", "order": 0},
            ],
        }

        result = ColorPalette.grouped_items_to_palette(grouped_items)

        assert len(result) == 4
        assert result["sectors"]["heating"] == "#FF0000"
        assert result["sectors"]["cooling"] == "#00FF00"
        assert result["scenarios"]["baseline"] == "#0000FF"

    def test_grouped_items_preserves_order(self) -> None:
        """Test that grouped items respects custom ordering."""
        grouped_items: dict[str, list[dict[str, Any]]] = {
            "Sectors": [
                {"label": "heating", "color": "#FF0000", "order": 1},
                {"label": "cooling", "color": "#00FF00", "order": 0},
            ],
        }

        result = ColorPalette.grouped_items_to_palette(grouped_items)

        # Convert back to list to check order
        keys = list(result["sectors"].keys())
        # cooling should come first because it has order 0
        assert keys[0] == "cooling"
        assert keys[1] == "heating"

    def test_round_trip_grouped_items(self) -> None:
        """Test round-trip conversion of grouped items."""
        palette = {
            "scenarios": {"baseline": "#0000FF"},
            "model_years": {},
            "sectors": {"heating": "#FF0000", "cooling": "#00FF00"},
            "end_uses": {},
        }

        # Convert to grouped items
        grouped_items: dict[str, list[dict[str, Any]]] = ColorPalette.palette_to_grouped_items(
            palette
        )

        # Convert back to palette
        result = ColorPalette.grouped_items_to_palette(grouped_items)

        # Should have same items (order might differ)
        assert result["scenarios"]["baseline"] == palette["scenarios"]["baseline"]
        assert result["sectors"]["heating"] == palette["sectors"]["heating"]
        assert result["sectors"]["cooling"] == palette["sectors"]["cooling"]

    def test_empty_groups(self) -> None:
        """Test handling of empty groups."""
        palette: dict[str, dict[str, str]] = {
            "scenarios": {},
            "model_years": {},
            "sectors": {},
            "end_uses": {},
        }

        result: dict[str, list[dict[str, Any]]] = ColorPalette.palette_to_grouped_items(palette)
        assert result == {}

        back = ColorPalette.grouped_items_to_palette(result)
        assert back == {"scenarios": {}, "model_years": {}, "sectors": {}, "end_uses": {}}


class TestLegacyMetricsCompat:
    """Test backward compatibility with the legacy 'metrics' key format."""

    def test_init_with_legacy_metrics_key(self) -> None:
        """Test that from_dict loads legacy 'metrics' entries into sectors."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": "#0000FF"},
                "model_years": {},
                "metrics": {"residential": "#FF0000", "commercial": "#00FF00"},
            }
        )
        assert palette.sectors["residential"] == "#FF0000"
        assert palette.sectors["commercial"] == "#00FF00"
        assert palette.scenarios["baseline"] == "#0000FF"

    def test_from_dict_with_legacy_metrics_key(self) -> None:
        """Test that from_dict loads legacy 'metrics' into sectors."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {},
                "model_years": {},
                "metrics": {"heating": "#FF0000"},
            }
        )
        assert palette.sectors["heating"] == "#FF0000"
        assert len(palette.end_uses) == 0

    def test_to_dict_emits_new_format(self) -> None:
        """Test that to_dict outputs the new 4-key format even after loading legacy."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {},
                "model_years": {},
                "metrics": {"heating": "#FF0000"},
            }
        )
        result = palette.to_dict()
        assert "sectors" in result
        assert "end_uses" in result
        assert "metrics" not in result
        assert result["sectors"]["heating"] == "#FF0000"

    def test_to_dict_legacy_emits_old_format(self) -> None:
        """Test that to_dict_legacy merges sectors and end_uses under 'metrics'."""
        palette = ColorPalette()
        palette.update("residential", "#FF0000", category=ColorCategory.SECTOR)
        palette.update("heating", "#00FF00", category=ColorCategory.END_USE)
        result = palette.to_dict_legacy()
        assert "metrics" in result
        assert "sectors" not in result
        assert "end_uses" not in result
        assert result["metrics"]["residential"] == "#FF0000"
        assert result["metrics"]["heating"] == "#00FF00"

    def test_init_with_new_4key_format(self) -> None:
        """Test that from_dict accepts the new 4-key format."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": "#0000FF"},
                "model_years": {"2020": "#AABBCC"},
                "sectors": {"residential": "#FF0000"},
                "end_uses": {"heating": "#00FF00"},
            }
        )
        assert palette.scenarios["baseline"] == "#0000FF"
        assert palette.model_years["2020"] == "#AABBCC"
        assert palette.sectors["residential"] == "#FF0000"
        assert palette.end_uses["heating"] == "#00FF00"

    def test_palette_to_grouped_items_legacy_compat(self) -> None:
        """Test that palette_to_grouped_items handles legacy 'metrics' key."""
        palette = {
            "scenarios": {},
            "model_years": {},
            "metrics": {"heating": "#FF0000", "cooling": "#00FF00"},
        }
        result = ColorPalette.palette_to_grouped_items(palette)
        assert "Sectors" in result
        assert len(result["Sectors"]) == 2


class TestMergeWithProjectDimensions:
    """Test ColorPalette.merge_with_project_dimensions."""

    def test_matched_names_keep_colors(self) -> None:
        """Entries in both palette and project keep their stored color."""
        palette = ColorPalette.from_dict(
            {"scenarios": {"baseline": "#AA0000", "high": "#BB0000"}, "model_years": {}, "sectors": {}, "end_uses": {}}
        )
        palette.merge_with_project_dimensions(scenarios=["baseline", "high"])
        assert palette.scenarios["baseline"] == "#AA0000"
        assert palette.scenarios["high"] == "#BB0000"

    def test_new_project_names_get_colors(self) -> None:
        """Names in the project but not in the palette get auto-assigned colors."""
        palette = ColorPalette.from_dict(
            {"scenarios": {"baseline": "#AA0000"}, "model_years": {}, "sectors": {}, "end_uses": {}}
        )
        palette.merge_with_project_dimensions(scenarios=["baseline", "new_scenario"])
        assert palette.scenarios["baseline"] == "#AA0000"
        assert "new_scenario" in palette.scenarios
        # New scenario should get a color different from the matched one
        assert palette.scenarios["new_scenario"] != "#AA0000"

    def test_extra_palette_entries_become_reserves(self) -> None:
        """Palette entries not in the project are kept as reserves at the end."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": "#AA0000", "old_scenario": "#BB0000"},
                "model_years": {},
                "sectors": {},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(scenarios=["baseline"])
        keys = list(palette.scenarios.keys())
        # Active entry first, reserve after
        assert keys[0] == "baseline"
        assert keys[1] == "old_scenario"
        # Colors preserved
        assert palette.scenarios["baseline"] == "#AA0000"
        assert palette.scenarios["old_scenario"] == "#BB0000"

    def test_reserve_colors_reused_before_theme(self) -> None:
        """New names should get reserve colors before cycling through the theme."""
        from stride.ui.palette import TOL_BRIGHT

        palette = ColorPalette.from_dict(
            {
                "scenarios": {"old_one": TOL_BRIGHT[0], "old_two": TOL_BRIGHT[1]},
                "model_years": {},
                "sectors": {},
                "end_uses": {},
            }
        )
        # Project has neither old name — both become reserves.
        # Two new names should reuse the reserve colors.
        palette.merge_with_project_dimensions(scenarios=["alpha", "beta"])
        assert palette.scenarios["alpha"] == TOL_BRIGHT[0]
        assert palette.scenarios["beta"] == TOL_BRIGHT[1]
        # Reserves still at the end
        assert list(palette.scenarios.keys()) == ["alpha", "beta", "old_one", "old_two"]

    def test_mixed_match_and_reserve_reuse(self) -> None:
        """Mix of matched, reserve-reuse, and fresh theme colors."""
        from stride.ui.palette import TOL_BRIGHT

        palette = ColorPalette.from_dict(
            {
                "scenarios": {
                    "baseline": TOL_BRIGHT[0],
                    "removed": TOL_BRIGHT[1],
                },
                "model_years": {},
                "sectors": {},
                "end_uses": {},
            }
        )
        # "baseline" matches, "removed" becomes reserve, "new_one" is new.
        palette.merge_with_project_dimensions(scenarios=["baseline", "new_one"])
        assert palette.scenarios["baseline"] == TOL_BRIGHT[0]
        # "new_one" should get the reserve color (TOL_BRIGHT[1]) before theme cycling
        assert palette.scenarios["new_one"] == TOL_BRIGHT[1]
        # "removed" is kept as reserve
        assert "removed" in palette.scenarios

    def test_multiple_categories(self) -> None:
        """Merge works across multiple categories simultaneously."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": "#AA0000"},
                "model_years": {},
                "sectors": {"residential": "#110000"},
                "end_uses": {"heating": "#220000"},
            }
        )
        palette.merge_with_project_dimensions(
            scenarios=["baseline", "new_sc"],
            sectors=["residential", "commercial"],
            end_uses=["heating", "cooling"],
        )
        assert "new_sc" in palette.scenarios
        assert "commercial" in palette.sectors
        assert "cooling" in palette.end_uses
        # Originals preserved
        assert palette.scenarios["baseline"] == "#AA0000"
        assert palette.sectors["residential"] == "#110000"
        assert palette.end_uses["heating"] == "#220000"

    def test_none_categories_skipped(self) -> None:
        """Passing None for a category leaves it untouched."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": "#AA0000"},
                "model_years": {},
                "sectors": {"residential": "#110000"},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(scenarios=["baseline"])
        # Sectors untouched (None was passed)
        assert palette.sectors == {"residential": "#110000"}

    def test_case_insensitive_matching(self) -> None:
        """Merge normalizes names to lowercase for matching."""
        palette = ColorPalette.from_dict(
            {"scenarios": {"baseline": "#AA0000"}, "model_years": {}, "sectors": {}, "end_uses": {}}
        )
        palette.merge_with_project_dimensions(scenarios=["Baseline"])
        assert palette.scenarios["baseline"] == "#AA0000"
        assert len(palette.scenarios) == 1
