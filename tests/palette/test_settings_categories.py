"""Test that all four color categories appear in the settings UI layout."""

from stride.ui.color_manager import ColorManager
from stride.ui.palette import ColorCategory, ColorPalette
from stride.ui.settings.layout import create_color_preview_content


def _extract_headings(content: list) -> list[str]:
    """Extract H6 heading text from the color preview content."""
    headings: list[str] = []
    for div in content:
        # Each category is wrapped in an html.Div whose first child is an H6
        if hasattr(div, "children") and div.children:
            first_child = div.children[0]
            if hasattr(first_child, "children") and isinstance(first_child.children, str):
                headings.append(first_child.children)
    return headings


def test_all_four_categories_in_color_preview() -> None:
    """All four category headings must appear in the settings color preview."""
    # Reset ColorManager singleton so we get a fresh instance
    ColorManager._instance = None  # type: ignore[misc]

    palette = ColorPalette()
    palette.update("baseline", "#AA0000", category=ColorCategory.SCENARIO)
    palette.update("2030", "#BB0000", category=ColorCategory.MODEL_YEAR)
    palette.update("residential", "#CC0000", category=ColorCategory.SECTOR)
    palette.update("heating", "#DD0000", category=ColorCategory.END_USE)

    cm = ColorManager(palette)
    content = create_color_preview_content(cm)

    headings = _extract_headings(content)
    assert "Scenarios" in headings, f"Missing 'Scenarios' heading; got {headings}"
    assert "Model Years" in headings, f"Missing 'Model Years' heading; got {headings}"
    assert "Sectors" in headings, f"Missing 'Sectors' heading; got {headings}"
    assert "End Uses" in headings, f"Missing 'End Uses' heading; got {headings}"

    # Clean up singleton
    ColorManager._instance = None  # type: ignore[misc]


def test_duplicate_label_across_categories_both_shown() -> None:
    """A label appearing in two categories must show up in both sections."""
    ColorManager._instance = None  # type: ignore[misc]

    palette = ColorPalette()
    palette.update("2025", "#AA0000", category=ColorCategory.MODEL_YEAR)
    palette.update("2025", "#BB0000", category=ColorCategory.SECTOR)

    cm = ColorManager(palette)
    content = create_color_preview_content(cm)

    headings = _extract_headings(content)
    assert "Model Years" in headings
    assert "Sectors" in headings

    # Count total color items — should have 2 (one per category)
    total_items = 0
    for div in content:
        if hasattr(div, "children") and len(div.children) >= 2:
            items_div = div.children[1]  # the flex-wrap div with color items
            if hasattr(items_div, "children"):
                total_items += len(items_div.children)

    assert total_items == 2, f"Expected 2 color items for duplicate label; got {total_items}"

    ColorManager._instance = None  # type: ignore[misc]
