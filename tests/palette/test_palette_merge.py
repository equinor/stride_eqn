"""Tests for ColorPalette.merge_with_project_dimensions."""

from stride.ui.palette import ColorPalette, TOL_BRIGHT


class TestMergeMatchedNames:
    """Matched names keep their stored color."""

    def test_all_names_match(self) -> None:
        """When palette and project have the same names, colors are preserved."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": "#111111", "high_growth": "#222222"},
                "model_years": {},
                "sectors": {},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(scenarios=["baseline", "high_growth"])
        assert palette.scenarios["baseline"] == "#111111"
        assert palette.scenarios["high_growth"] == "#222222"

    def test_sectors_match(self) -> None:
        """Sector name matching preserves colors."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {},
                "model_years": {},
                "sectors": {"residential": "#AA0000", "commercial": "#BB0000"},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(sectors=["residential", "commercial"])
        assert palette.sectors["residential"] == "#AA0000"
        assert palette.sectors["commercial"] == "#BB0000"


class TestMergeUnmatchedProjectNames:
    """Project names not in palette get new theme colors, skipping used ones."""

    def test_extra_project_scenarios(self) -> None:
        """Project has more scenarios than the palette — extras get theme colors."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": TOL_BRIGHT[0]},
                "model_years": {},
                "sectors": {},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(
            scenarios=["baseline", "new_scenario_1", "new_scenario_2"]
        )
        assert palette.scenarios["baseline"] == TOL_BRIGHT[0]
        # New entries should get colors, and they shouldn't duplicate the matched color
        new1 = palette.scenarios["new_scenario_1"]
        new2 = palette.scenarios["new_scenario_2"]
        assert new1 != TOL_BRIGHT[0]
        assert new2 != TOL_BRIGHT[0]
        assert new1 != new2

    def test_completely_new_scenarios(self) -> None:
        """Project has entirely different scenario names — all get fresh colors."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"old_scenario": "#AAAAAA"},
                "model_years": {},
                "sectors": {},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(scenarios=["alpha", "beta"])
        # Alpha and beta should have colors
        assert "alpha" in palette.scenarios
        assert "beta" in palette.scenarios
        # Old scenario should still be present as reserve
        assert "old_scenario" in palette.scenarios

    def test_skips_used_colors(self) -> None:
        """New entries skip colors already used by matched entries."""
        # Give baseline the first TOL_BRIGHT color
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": TOL_BRIGHT[0]},
                "model_years": {},
                "sectors": {},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(scenarios=["baseline", "extra"])
        # "extra" should NOT get TOL_BRIGHT[0] since it's used by "baseline"
        assert palette.scenarios["extra"] != TOL_BRIGHT[0]


class TestMergeReserveEntries:
    """Extra palette entries not in the project are kept as reserves."""

    def test_reserves_kept(self) -> None:
        """Palette entries not in the project remain and appear after active entries."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {
                    "reserve_1": "#111111",
                    "reserve_2": "#222222",
                    "active": "#333333",
                },
                "model_years": {},
                "sectors": {},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(scenarios=["active"])
        # Active entry is preserved
        assert palette.scenarios["active"] == "#333333"
        # Reserves are kept
        assert palette.scenarios["reserve_1"] == "#111111"
        assert palette.scenarios["reserve_2"] == "#222222"
        # Active entry comes first in iteration order
        keys = list(palette.scenarios.keys())
        assert keys[0] == "active"

    def test_large_user_palette_reserves(self) -> None:
        """A user palette with 20 sector colors applied to an 8-sector project."""
        big_palette_data: dict[str, str] = {}
        for i in range(20):
            big_palette_data[f"sector_{i}"] = f"#{i:02x}{i:02x}{i:02x}"

        palette = ColorPalette.from_dict(
            {
                "scenarios": {},
                "model_years": {},
                "sectors": big_palette_data,
                "end_uses": {},
            }
        )

        project_sectors = [f"sector_{i}" for i in range(8)]
        palette.merge_with_project_dimensions(sectors=project_sectors)

        # All 20 entries should still exist
        assert len(palette.sectors) == 20
        # First 8 keys should be the project sectors
        keys = list(palette.sectors.keys())
        assert keys[:8] == project_sectors
        # Colors are preserved for matched entries
        for i in range(8):
            assert palette.sectors[f"sector_{i}"] == f"#{i:02x}{i:02x}{i:02x}"


class TestMergeOrdering:
    """Merged palette has project entries first, then reserves."""

    def test_project_order_preserved(self) -> None:
        """Active entries appear in the order provided by the project."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"c": "#CC0000", "a": "#AA0000", "b": "#BB0000"},
                "model_years": {},
                "sectors": {},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(scenarios=["b", "a"])
        keys = list(palette.scenarios.keys())
        assert keys[0] == "b"
        assert keys[1] == "a"
        # "c" is a reserve and comes after
        assert keys[2] == "c"


class TestMergeMultipleCategories:
    """Merge can operate on multiple categories at once."""

    def test_merge_scenarios_and_sectors(self) -> None:
        """Merging affects both scenarios and sectors simultaneously."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": "#111111"},
                "model_years": {},
                "sectors": {"residential": "#AAAAAA"},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(
            scenarios=["baseline", "high"],
            sectors=["residential", "commercial"],
        )
        assert len(palette.scenarios) == 2
        assert len(palette.sectors) == 2
        assert palette.scenarios["baseline"] == "#111111"
        assert palette.sectors["residential"] == "#AAAAAA"
        # New entries have valid hex colors
        assert palette.scenarios["high"].startswith("#")
        assert palette.sectors["commercial"].startswith("#")

    def test_none_categories_skipped(self) -> None:
        """Categories passed as None are not touched."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {"baseline": "#111111"},
                "model_years": {},
                "sectors": {"residential": "#AAAAAA"},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(scenarios=["baseline"])
        # Sectors should be untouched
        assert palette.sectors["residential"] == "#AAAAAA"
        assert len(palette.sectors) == 1


class TestMergeCaseInsensitive:
    """Merge handles case normalization."""

    def test_mixed_case_matching(self) -> None:
        """Project names with different casing still match palette entries."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {},
                "model_years": {},
                "sectors": {"residential": "#FF0000"},
                "end_uses": {},
            }
        )
        palette.merge_with_project_dimensions(sectors=["Residential"])
        # Should match (keys are lowered)
        assert "residential" in palette.sectors
        assert palette.sectors["residential"] == "#FF0000"


class TestMergeEndUses:
    """End uses merge correctly with their own theme."""

    def test_end_uses_merge(self) -> None:
        """End uses get metric theme colors for new entries."""
        palette = ColorPalette.from_dict(
            {
                "scenarios": {},
                "model_years": {},
                "sectors": {},
                "end_uses": {"heating": "#FF0000"},
            }
        )
        palette.merge_with_project_dimensions(end_uses=["heating", "cooling", "lighting"])
        assert palette.end_uses["heating"] == "#FF0000"
        assert "cooling" in palette.end_uses
        assert "lighting" in palette.end_uses
        assert len(palette.end_uses) == 3
