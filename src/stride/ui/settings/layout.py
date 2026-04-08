"""Settings page layout for STRIDE dashboard."""

import os

import dash_bootstrap_components as dbc
from dash import dcc, html

from stride.ui.color_manager import ColorManager
from stride.ui.palette import ColorCategory

# Store for temporarily edited colors before saving.
# Keys are composite ``"category_value:label"`` strings (e.g.
# ``"scenarios:baseline"``).
_temp_color_edits: dict[str, str] = {}


def create_settings_layout(
    project_palette_name: str,
    user_palettes: list[str],
    current_palette_type: str,
    current_palette_name: str | None,
    color_manager: ColorManager,
    default_user_palette: str | None = None,
) -> html.Div:
    """
    Create the settings page layout.

    Parameters
    ----------
    project_palette_name : str
        Name of the project's palette
    user_palettes : list[str]
        List of available user palette names
    current_palette_type : str
        Currently active palette type ('project' or 'user')
    current_palette_name : str | None
        Name of currently active user palette (if type is 'user')
    color_manager : ColorManager
        Color manager instance for displaying current colors
    default_user_palette : str | None
        Name of the current default user palette, or None if not set

    Returns
    -------
    html.Div
        Settings page layout
    """
    # Get current palette data from color manager's palette
    palette = color_manager.get_palette()

    # Get structured palette with categories
    structured_palette = palette.to_dict()

    # Extract colors for each category and convert to RGBA for display.
    scenario_colors = {}
    for label in structured_palette.get("scenarios", {}):
        scenario_colors[label] = color_manager.get_color(label, ColorCategory.SCENARIO)

    model_year_colors = {}
    for label in structured_palette.get("model_years", {}):
        model_year_colors[label] = color_manager.get_color(label, ColorCategory.MODEL_YEAR)

    sector_colors = {}
    for label in structured_palette.get("sectors", {}):
        sector_colors[label] = color_manager.get_color(label, ColorCategory.SECTOR)

    end_use_colors = {}
    for label in structured_palette.get("end_uses", {}):
        end_use_colors[label] = color_manager.get_color(label, ColorCategory.END_USE)

    # Get temporary color edits
    temp_edits = get_temp_color_edits()

    # Resolve max cached projects override state for the General section
    from stride.ui.app import (
        _max_cached_projects_override,
        get_max_cached_projects,
    )

    max_cached_value = get_max_cached_projects()
    override_source = None
    if _max_cached_projects_override is not None:
        override_source = f"CLI flag (--max-cached-projects {_max_cached_projects_override})"
    elif os.environ.get("STRIDE_MAX_CACHED_PROJECTS") is not None:
        override_source = f"Environment variable (STRIDE_MAX_CACHED_PROJECTS={os.environ['STRIDE_MAX_CACHED_PROJECTS']})"
    is_overridden = override_source is not None

    override_badge = []
    if is_overridden:
        override_badge = [
            dbc.Badge(
                f"Overridden by: {override_source}",
                color="warning",
                className="ms-2 mb-2",
            ),
        ]

    return html.Div(
        [
            dbc.Container(
                [
                    # Header
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H2("Settings", className="mb-4"),
                                    html.Hr(),
                                ]
                            )
                        ]
                    ),
                    # General Settings Section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H4("General", className="mb-3"),
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.Label(
                                                        "Max Cached Projects:",
                                                        className="form-label fw-bold",
                                                    ),
                                                    *override_badge,
                                                    html.Div(
                                                        [
                                                            dcc.Input(
                                                                id="max-cached-projects-input",
                                                                type="number",
                                                                step=1,
                                                                value=max_cached_value,
                                                                className="form-control form-control-sm",
                                                                style={"width": "100px", "display": "inline-block", "height": "31px", "fontSize": "0.85rem"},
                                                                readOnly=is_overridden,
                                                                disabled=is_overridden,
                                                            ),
                                                            dbc.Button(
                                                                "Save",
                                                                id="save-max-cached-btn",
                                                                color="primary",
                                                                size="sm",
                                                                className="ms-2",
                                                                disabled=is_overridden,
                                                            ),
                                                        ],
                                                        className="d-flex align-items-center mb-2",
                                                    ),
                                                    html.Small(
                                                        "Number of projects to keep open simultaneously. "
                                                        "Each open project holds a database connection; "
                                                        "too many concurrent connections may cause errors on network-mounted filesystems.",
                                                        className="text-muted",
                                                    ),
                                                    html.Div(
                                                        id="max-cached-projects-status",
                                                        className="mt-2",
                                                    ),
                                                ]
                                            )
                                        ],
                                        className="mb-4",
                                    ),
                                ]
                            )
                        ],
                        className="mb-4",
                    ),
                    # Palette Selection Section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H4("Color Palette", className="mb-3"),
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.Label(
                                                        "Select Palette Source:",
                                                        className="form-label fw-bold",
                                                    ),
                                                    dbc.RadioItems(
                                                        id="palette-type-selector",
                                                        options=[
                                                            {
                                                                "label": f"Project Palette ({project_palette_name})",
                                                                "value": "project",
                                                            },
                                                            {
                                                                "label": "User Palette",
                                                                "value": "user",
                                                            },
                                                        ],
                                                        value=current_palette_type,
                                                        className="mb-3",
                                                    ),
                                                    html.Div(
                                                        [
                                                            html.Label(
                                                                "Select User Palette:",
                                                                className="form-label",
                                                            ),
                                                            dcc.Dropdown(
                                                                id="user-palette-selector",
                                                                options=[
                                                                    {"label": p, "value": p}  # type: ignore[arg-type]
                                                                    for p in user_palettes
                                                                ],
                                                                value=current_palette_name,
                                                                placeholder="Select a user palette...",
                                                                disabled=(
                                                                    current_palette_type
                                                                    != "user"
                                                                ),
                                                            ),
                                                            dbc.Button(
                                                                "Delete",
                                                                id="delete-user-palette-btn",
                                                                color="danger",
                                                                outline=True,
                                                                size="sm",
                                                                className="ms-2 mt-2",
                                                                disabled=(
                                                                    current_palette_type
                                                                    != "user"
                                                                    or not current_palette_name
                                                                ),
                                                            ),
                                                            dbc.Button(
                                                                (
                                                                    "Dashboard Default ✓ (Clear)"
                                                                    if (
                                                                        current_palette_name
                                                                        and current_palette_name
                                                                        == default_user_palette
                                                                    )
                                                                    else "Set as Dashboard Default"
                                                                ),
                                                                id="set-default-palette-btn",
                                                                color=(
                                                                    "success"
                                                                    if (
                                                                        current_palette_name
                                                                        and current_palette_name
                                                                        == default_user_palette
                                                                    )
                                                                    else "secondary"
                                                                ),
                                                                outline=True,
                                                                size="sm",
                                                                className="ms-2 mt-2 theme-text",
                                                                disabled=(
                                                                    current_palette_type
                                                                    != "user"
                                                                    or not current_palette_name
                                                                ),
                                                            ),
                                                        ],
                                                        id="user-palette-selector-container",
                                                        style={
                                                            "display": (
                                                                "block"
                                                                if current_palette_type == "user"
                                                                else "none"
                                                            )
                                                        },
                                                    ),
                                                    # Palette source hint (shown dynamically)
                                                    html.Div(
                                                        id="palette-source-hint",
                                                        className="mt-2",
                                                    ),
                                                    # Unsaved changes indicator (shown dynamically)
                                                    html.Div(
                                                        id="unsaved-changes-indicator",
                                                    ),
                                                    # Reset to Defaults button
                                                    dbc.Button(
                                                        "Reset to Defaults",
                                                        id="reset-to-defaults-btn",
                                                        color="secondary",
                                                        outline=True,
                                                        size="sm",
                                                        className="mt-3",
                                                    ),
                                                ]
                                            )
                                        ],
                                        className="mb-4",
                                    ),
                                ]
                            )
                        ]
                    ),
                    # Current Colors Preview Section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H4("Current Color Scheme", className="mb-3"),
                                    html.P(
                                        "Click any color to edit it with the color picker.",
                                        className="text-muted small mb-3",
                                    ),
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                id="color-preview-container",
                                                children=[
                                                    # Scenarios
                                                    html.Div(
                                                        [
                                                            html.H6(
                                                                "Scenarios",
                                                                className="mb-2 text-muted",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    _create_color_item(
                                                                        ColorCategory.SCENARIO.value, label, color, temp_edits
                                                                    )
                                                                    for label, color in scenario_colors.items()
                                                                ],
                                                                className="d-flex flex-wrap gap-2 mb-3",
                                                            ),
                                                        ]
                                                    )
                                                    if scenario_colors
                                                    else None,
                                                    # Model Years
                                                    html.Div(
                                                        [
                                                            html.H6(
                                                                "Model Years",
                                                                className="mb-2 text-muted",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    _create_color_item(
                                                                        ColorCategory.MODEL_YEAR.value, label, color, temp_edits
                                                                    )
                                                                    for label, color in model_year_colors.items()
                                                                ],
                                                                className="d-flex flex-wrap gap-2 mb-3",
                                                            ),
                                                        ]
                                                    )
                                                    if model_year_colors
                                                    else None,
                                                    # Metrics
                                                    html.Div(
                                                        [
                                                            html.H6(
                                                                "Sectors",
                                                                className="mb-2 text-muted",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    _create_color_item(
                                                                        ColorCategory.SECTOR.value, label, color, temp_edits
                                                                    )
                                                                    for label, color in sector_colors.items()
                                                                ],
                                                                className="d-flex flex-wrap gap-2 mb-3",
                                                            ),
                                                        ]
                                                    )
                                                    if sector_colors
                                                    else None,
                                                    # End Uses
                                                    html.Div(
                                                        [
                                                            html.H6(
                                                                "End Uses",
                                                                className="mb-2 text-muted",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    _create_color_item(
                                                                        ColorCategory.END_USE.value, label, color, temp_edits
                                                                    )
                                                                    for label, color in end_use_colors.items()
                                                                ],
                                                                className="d-flex flex-wrap gap-2",
                                                            ),
                                                        ]
                                                    )
                                                    if end_use_colors
                                                    else None,
                                                ],
                                            )
                                        ],
                                        className="mb-4",
                                    ),
                                ]
                            )
                        ]
                    ),
                    # JSON Editor Section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Div(
                                        [
                                            html.H4("Advanced: JSON Editor", className="mb-2"),
                                            dbc.Button(
                                                [
                                                    html.I(className="bi bi-chevron-down me-2"),
                                                    "Show JSON Editor",
                                                ],
                                                id="toggle-json-editor-btn",
                                                color="secondary",
                                                outline=True,
                                                size="sm",
                                                className="mb-3",
                                            ),
                                        ]
                                    ),
                                    dbc.Collapse(
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.P(
                                                            "Edit the palette as JSON. Paste a new palette and click 'Apply JSON' to update the preview. Changes are not saved until you use one of the save buttons below.",
                                                            className="text-muted small mb-3",
                                                        ),
                                                        dbc.Textarea(
                                                            id="palette-json-editor",
                                                            style={
                                                                "fontFamily": "monospace",
                                                                "fontSize": "0.85rem",
                                                                "minHeight": "300px",
                                                            },
                                                            className="mb-3",
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Button(
                                                                    "Apply JSON",
                                                                    id="apply-json-btn",
                                                                    color="primary",
                                                                    size="sm",
                                                                    className="me-2",
                                                                ),
                                                                dbc.Button(
                                                                    "Reset to Current",
                                                                    id="reset-json-btn",
                                                                    color="secondary",
                                                                    size="sm",
                                                                ),
                                                            ],
                                                            className="mb-2",
                                                        ),
                                                        html.Div(id="json-editor-status"),
                                                    ]
                                                )
                                            ],
                                            className="mb-4",
                                        ),
                                        id="json-editor-collapse",
                                        is_open=False,
                                    ),
                                ]
                            )
                        ]
                    ),
                    # Color Picker Modal
                    dbc.Modal(
                        [
                            dbc.ModalHeader(
                                dbc.ModalTitle(id="color-picker-modal-title"),
                                close_button=True,
                            ),
                            dbc.ModalBody(
                                [
                                    html.Div(
                                        [
                                            html.Label(
                                                "Select Color:",
                                                className="form-label fw-bold mb-2",
                                            ),
                                            html.Div(
                                                [
                                                    dbc.Input(
                                                        id="color-picker-input",
                                                        type="color",  # type: ignore[arg-type]
                                                        style={
                                                            "width": "100%",
                                                            "height": "60px",
                                                            "cursor": "pointer",
                                                        },
                                                    ),
                                                ],
                                                className="mb-3",
                                            ),
                                            html.Div(
                                                [
                                                    html.Label(
                                                        "Or enter hex color:",
                                                        className="form-label mb-2",
                                                    ),
                                                    dbc.Input(
                                                        id="color-picker-hex-input",
                                                        type="text",
                                                        placeholder="#RRGGBB",
                                                        debounce=True,
                                                    ),
                                                ],
                                                className="mb-3",
                                            ),
                                        ]
                                    ),
                                ]
                            ),
                            dbc.ModalFooter(
                                [
                                    dbc.Button(
                                        "Cancel",
                                        id="color-picker-cancel-btn",
                                        color="secondary",
                                        className="me-2",
                                    ),
                                    dbc.Button(
                                        "Apply",
                                        id="color-picker-apply-btn",
                                        color="primary",
                                    ),
                                ]
                            ),
                        ],
                        id="color-picker-modal",
                        is_open=False,
                        size="md",
                        centered=True,
                    ),
                    # Delete Confirmation Modal
                    dbc.Modal(
                        [
                            dbc.ModalHeader(
                                dbc.ModalTitle("Confirm Delete"),
                                close_button=True,
                            ),
                            dbc.ModalBody(
                                [
                                    html.P(
                                        id="delete-confirmation-text",
                                        className="mb-0",
                                    ),
                                ]
                            ),
                            dbc.ModalFooter(
                                [
                                    dbc.Button(
                                        "Cancel",
                                        id="delete-cancel-btn",
                                        color="secondary",
                                        className="me-2",
                                    ),
                                    dbc.Button(
                                        "Delete",
                                        id="delete-confirm-btn",
                                        color="danger",
                                    ),
                                ]
                            ),
                        ],
                        id="delete-confirmation-modal",
                        is_open=False,
                        size="md",
                        centered=True,
                    ),
                    # Hidden store for selected color label
                    dcc.Store(id="selected-color-label", data=None),
                    # Hidden store for tracking color edits (triggers refresh)
                    dcc.Store(id="color-edits-counter", data=0),
                    # Hidden store for tracking the current default user palette
                    dcc.Store(id="default-user-palette-store", data=default_user_palette),
                    # Save Options Section
                    dbc.Row(
                        html.Div(
                            [
                                dbc.Col(
                                    [
                                        html.H4("Save Options", className="mb-3"),
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.P(
                                                            "Save the current color scheme:",
                                                            className="mb-3",
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Button(
                                                                    "Save to Project",
                                                                    id="save-to-project-btn",
                                                                    color="success",
                                                                    outline=True,
                                                                    className="m-1 theme-text",
                                                                ),
                                                                dbc.Button(
                                                                    "Save As User Palette",
                                                                    id="save-to-new-palette-btn",
                                                                    color="info",
                                                                    outline=True,
                                                                    className="m-1 theme-text",
                                                                ),
                                                                dbc.Button(
                                                                    "Revert Changes",
                                                                    id="revert-changes-btn",
                                                                    color="secondary",
                                                                    outline=True,
                                                                    className="m-1 theme-text",
                                                                ),
                                                            ],
                                                            className="d-flex flex-wrap mb-3",
                                                        ),
                                                        html.Div(id="revert-changes-status"),
                                                        html.Div(id="delete-palette-status"),
                                                        html.Div(id="save-palette-status"),
                                                        # New palette name input (hidden by default)
                                                        html.Div(
                                                            [
                                                                html.Label(
                                                                    "New Palette Name:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="save-new-palette-name",
                                                                    type="text",
                                                                    placeholder="Enter new palette name...",
                                                                ),
                                                            ],
                                                            id="save-new-palette-name-container",
                                                            style={"display": "none"},
                                                            className="mt-3",
                                                        ),
                                                    ]
                                                )
                                            ],
                                            className="mb-4",
                                        ),
                                    ]
                                )
                            ],
                        )
                    ),
                    # Back button
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Button(
                                        "← Back to Dashboard",
                                        id="back-to-dashboard-btn",
                                        color="secondary",
                                        className="mb-4",
                                    )
                                ]
                            )
                        ]
                    ),
                ],
                fluid=True,
                className="mt-4",
            )
        ]
    )


def _create_color_item(
    category: str, label: str, color: str, temp_edits: dict[str, str]
) -> html.Div:
    """
    Create a color preview item with label.

    Parameters
    ----------
    category : str
        Category value string (e.g. ``"scenarios"``, ``"model_years"``).
    label : str
        Label name
    color : str
        Color value (hex, rgb, or rgba)
    temp_edits : dict[str, str]
        Dictionary of temporary color edits (composite key → color)

    Returns
    -------
    html.Div
        Color preview component
    """
    composite_key = f"{category}:{label}"
    # Check if there's a temporary edit for this color
    display_color = temp_edits.get(composite_key, color)

    return html.Div(
        [
            html.Button(
                [
                    html.Div(
                        style={
                            "width": "30px",
                            "height": "30px",
                            "backgroundColor": display_color,
                            "border": "1px solid #ddd",
                            "borderRadius": "4px",
                            "display": "inline-block",
                            "verticalAlign": "middle",
                        }
                    ),
                    html.Span(
                        label,
                        style={
                            "marginLeft": "8px",
                            "verticalAlign": "middle",
                            "fontSize": "0.9rem",
                        },
                    ),
                ],
                id={"type": "color-item", "index": composite_key},
                n_clicks=0,
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "padding": "6px 12px",
                    "backgroundColor": "#f8f9fa",
                    "borderRadius": "4px",
                    "border": "1px solid #dee2e6",
                    "cursor": "pointer",
                    "transition": "all 0.2s",
                },
                className="color-item-button",
            ),
        ],
        **{"data-color-label": label},  # type: ignore[arg-type]
    )


def get_temp_color_edits() -> dict[str, str]:
    """Get the temporary color edits dictionary.

    Keys are composite ``"category_value:label"`` strings.
    """
    return _temp_color_edits


def clear_temp_color_edits() -> None:
    """Clear all temporary color edits."""
    _temp_color_edits.clear()


def set_temp_color_edit(composite_key: str, color: str) -> None:
    """Set a temporary color edit.

    Parameters
    ----------
    composite_key : str
        Key in ``"category_value:label"`` format.
    color : str
        Hex color string.
    """
    _temp_color_edits[composite_key] = color


def parse_temp_edit_key(composite_key: str) -> tuple[str, str]:
    """Split a composite temp-edit key into ``(category_value, label)``.

    Parameters
    ----------
    composite_key : str
        Key in ``"category_value:label"`` format.

    Returns
    -------
    tuple[str, str]
        ``(category_value, label)``
    """
    category, _, label = composite_key.partition(":")
    return category, label


def get_temp_edits_for_category(category_value: str) -> dict[str, str]:
    """Return temp edits for one category with plain label keys.

    Parameters
    ----------
    category_value : str
        The ``ColorCategory`` ``.value`` string, e.g. ``"scenarios"``.

    Returns
    -------
    dict[str, str]
        ``{label: color}`` for entries matching the given category.
    """
    prefix = f"{category_value}:"
    return {
        key[len(prefix):]: color
        for key, color in _temp_color_edits.items()
        if key.startswith(prefix)
    }


def create_color_preview_content(color_manager: ColorManager) -> list[html.Div]:
    """
    Create the color preview content with current colors and temp edits.

    Parameters
    ----------
    color_manager : ColorManager
        Color manager instance for displaying current colors

    Returns
    -------
    list
        List of HTML components for the color preview
    """
    # Get current palette data from color manager's palette
    palette = color_manager.get_palette()

    # Get structured palette with categories
    structured_palette = palette.to_dict()

    # Extract colors for each category and convert to RGBA for display.
    scenario_colors = {}
    for label in structured_palette.get("scenarios", {}):
        scenario_colors[label] = color_manager.get_color(label, ColorCategory.SCENARIO)

    model_year_colors = {}
    for label in structured_palette.get("model_years", {}):
        model_year_colors[label] = color_manager.get_color(label, ColorCategory.MODEL_YEAR)

    sector_colors = {}
    for label in structured_palette.get("sectors", {}):
        sector_colors[label] = color_manager.get_color(label, ColorCategory.SECTOR)

    end_use_colors = {}
    for label in structured_palette.get("end_uses", {}):
        end_use_colors[label] = color_manager.get_color(label, ColorCategory.END_USE)

    # Get temporary color edits
    temp_edits = get_temp_color_edits()

    # Build the content
    content = []

    # Scenarios
    if scenario_colors:
        content.append(
            html.Div(
                [
                    html.H6(
                        "Scenarios",
                        className="mb-2 text-muted",
                    ),
                    html.Div(
                        [
                            _create_color_item(ColorCategory.SCENARIO.value, label, color, temp_edits)
                            for label, color in scenario_colors.items()
                        ],
                        className="d-flex flex-wrap gap-2 mb-3",
                    ),
                ]
            )
        )

    # Model Years
    if model_year_colors:
        content.append(
            html.Div(
                [
                    html.H6(
                        "Model Years",
                        className="mb-2 text-muted",
                    ),
                    html.Div(
                        [
                            _create_color_item(ColorCategory.MODEL_YEAR.value, label, color, temp_edits)
                            for label, color in model_year_colors.items()
                        ],
                        className="d-flex flex-wrap gap-2 mb-3",
                    ),
                ]
            )
        )

    # Sectors
    if sector_colors:
        content.append(
            html.Div(
                [
                    html.H6(
                        "Sectors",
                        className="mb-2 text-muted",
                    ),
                    html.Div(
                        [
                            _create_color_item(ColorCategory.SECTOR.value, label, color, temp_edits)
                            for label, color in sector_colors.items()
                        ],
                        className="d-flex flex-wrap gap-2 mb-3",
                    ),
                ]
            )
        )

    # End Uses
    if end_use_colors:
        content.append(
            html.Div(
                [
                    html.H6(
                        "End Uses",
                        className="mb-2 text-muted",
                    ),
                    html.Div(
                        [
                            _create_color_item(ColorCategory.END_USE.value, label, color, temp_edits)
                            for label, color in end_use_colors.items()
                        ],
                        className="d-flex flex-wrap gap-2",
                    ),
                ]
            )
        )

    return content
