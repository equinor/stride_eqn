# Palette Redesign Plan

## Overview

Redesign the color palette system to fix usability issues in the settings UI,
improve palette portability across projects, split the combined "metrics"
category into separate "sectors" and "end_uses", simplify save actions, and
remove the redundant TUI palette editor.

---

## Phase 1 — Serialization Format Change ✅

**Status:** Complete. All 387 tests pass.

**Goal:** Make the on-disk format match the internal model (sectors + end_uses
stored separately instead of merged under "metrics").

### Changes

- **`ColorPalette.to_dict()`** — Emit `{"scenarios": {…}, "model_years": {…},
  "sectors": {…}, "end_uses": {…}}`.  Add a legacy helper `to_dict_legacy()`
  that returns the old 3-key format for any code that still needs it.

- **`ColorPalette.__init__`** — Accept the new 4-key format *or* the old 3-key
  format (with `"metrics"` loaded into `sectors`).

- **`ColorPalette.from_dict()`** — Same backward-compat logic.

- **`ColorPalette.get_display_items()`** — Return four groups
  (`scenarios`, `model_years`, `sectors`, `end_uses`) instead of merging
  sectors/end_uses under `"metrics"`.

- **`ProjectConfig.color_palette`** (models.py) — Change the Field default to
  `{"scenarios": {}, "model_years": {}, "sectors": {}, "end_uses": {}}`.
  The Pydantic model must still accept the old 3-key shape on load (validated
  in `ColorPalette.__init__`).

- **`Project.save_palette()`** — Writes the new 4-key format.

- **Settings layout** (layout.py) — Display four groups in the color preview.

- **Settings callbacks** (callbacks.py) — Update `create_color_preview_content`
  to iterate four categories.

### Backward Compatibility

Old `project.json5` files with `{"scenarios":{}, "model_years":{}, "metrics":{}}`
remain loadable.  On next `save_palette()` they are rewritten in the new format.

### Tests

- Update `test_palette.py` round-trip tests for the new 4-key format.
- Add a test that loads the old 3-key format and verifies metrics land in
  `sectors`.
- Update any test that calls `to_dict()` and asserts on the `"metrics"` key.

### Docs

- Update `docs/explanation/customizing_checks.md` or palette-related docs if
  they reference the old format.

---

## Phase 2 — Minimal/Full Palettes & `from_dict()` Classmethod ✅

**Status:** Implementation complete. All production and test call sites
migrated. 387 tests pass. Docs items deferred to Phase 5.

**Goal:** Make palettes robust when shared across projects whose scenario /
sector / end-use names differ.  Introduce *minimal* vs *full* palettes and
replace the dict-in-`__init__` pattern with `ColorPalette.from_dict()`.

### Palette Variants

| Variant  | Description |
|----------|-------------|
| Minimal  | Name→color assignments only.  Missing names get colors from the **default** TOL themes. |
| Full     | Name→color assignments **plus** custom color cycles per category.  Missing names draw from the user-supplied themes instead of the built-in TOL palettes. |

Discrimination is based on the presence of a `"themes"` key in the serialized
dict.  The `"themes"` key is a dict of category→list-of-hex-strings:

```json
{
  "scenarios": {"baseline": "#4477AA"},
  "sectors": {"residential": "#CC6677"},
  "end_uses": {},
  "model_years": {},
  "themes": {
    "scenarios": ["#4477AA", "#CCBB44", "#228833"],
    "sectors": ["#CC6677", "#999933", "#5289C7"],
    "end_uses": ["#CC6677", "#999933", "#5289C7"],
    "model_years": ["#9D7DB2", "#906388", "#805770"]
  }
}
```

A minimal palette omits `"themes"` entirely (equivalent to the built-in TOL
palettes).  `to_dict()` only includes `"themes"` when they differ from the
defaults.

### Constructor Refactoring

- **`__init__`** — Drop the `palette` parameter.  Accept only keyword-only
  theme overrides: `scenario_theme`, `model_year_theme`, `metric_theme`.
  Default to the TOL palettes when `None`.
- **`from_dict(data)`** — Detects structured/flat/legacy formats,
  extracts `"themes"` if present, constructs the instance with custom themes,
  populates name→color entries.  Replaces `__init__(palette=…)`.
- **`copy()`** — Uses `from_dict(self.to_dict())` instead of `__init__(self.to_dict())`.
- All production call sites (`project.py`, `tui.py`, `callbacks.py`) switch
  from `ColorPalette(dict)` to `ColorPalette.from_dict(dict)`.

### Merge Logic

Method `merge_with_project_dimensions(scenarios, sectors, end_uses,
model_years)` performs per-category merging:

1. **Matched names** — in both palette and project — keep their stored color.
2. **Reserve collection** — palette entries not in the project are set aside.
   Their colors return to the front of the available-color pool.
3. **New-name assignment** — project names not in the palette draw colors from
   the reserve pool first, then from the theme (skipping matched colors).

Reserve entries stay in the category dict (after the active entries) so they
remain visible in the settings UI and their colors can be reassigned to other
labels.

### Tests

- Palette with 3 scenarios applied to project with 5 scenarios.
- Palette with different scenario names than the project.
- Reserve colors reused before theme colors for new names.
- User palette with 20 sector colors applied to an 8-sector project.
- Full palette with custom themes round-trips through `to_dict()` / `from_dict()`.
- Minimal palette `to_dict()` omits `"themes"`.

### Docs

- Document the merge behavior in `docs/explanation/customizing_checks.md`.
- Document minimal vs full palette formats.

---

## Phase 3 — Settings UI Overhaul ✅

**Status:** Complete. All 404 tests pass (387 main + 17 TUI).

**Goal:** Simplify the settings pane: add "Default" palette source, "Reset to
Defaults" button, collapse save actions, show sectors / end uses separately.

### Palette Source Radio (3-way)

| Option    | Meaning |
|-----------|---------|
| Default   | No stored colors. Fresh assignment from TOL themes each session. |
| Project   | Name→color mappings from `project.json5`. |
| User      | Name→color mappings from `~/.stride/palettes/*.json`. |

- Selecting "Default" clears the active palette in memory (does NOT write to
  disk) and recomputes colors from themes + project dimensions.
- Editing a color while on "Default" creates unsaved temp edits.  You must
  "Save to Project" or "Save As User Palette" to persist.

### Save Actions (simplified)

| Button              | Action |
|---------------------|--------|
| Save to Project     | Write current colors (incl edits) to `project.json5`. |
| Save As User Palette | Prompt for name, write to `~/.stride/palettes/`. |
| Revert Changes      | Discard unsaved edits, reload from disk / recompute. |

"Save Current Palette" and the separate "Save to Project" are collapsed into
one "Save to Project".  "Delete User Palette" moves next to the user palette
dropdown.

### Reset to Defaults

A button that switches the radio to "Default" and recomputes.  Equivalent to
clicking the Default radio.

### Tests

- Test that callbacks wire up correctly for the new radio options.

### Docs

- Update `docs/how_tos/customize_palette.md` for the new UI layout.
- Update screenshots if any.

---

## Phase 4 — Remove TUI

**Status:** Not started.

**Goal:** Eliminate the Textual TUI palette editor.  Palette editing lives
exclusively in the web UI (`stride view` → Settings).

### Changes

- Delete the `PaletteViewer` class and related TUI code from `tui.py`.
- Keep utility functions (`load_user_palette`, `save_user_palette`,
  `list_user_palettes`, `get_default_user_palette`, `set_default_user_palette`,
  `delete_user_palette`) — move to a standalone module if cleaner.
- Update `stride palette view` CLI command: remove it (or repurpose to open the
  web UI).
- Keep `stride palette list`, `stride palette set-default`,
  `stride palette get-default`, `stride palette init`.

### Tests

- Remove TUI-specific tests.
- Ensure CLI tests still pass for remaining commands.

### Docs

- Remove TUI references from docs.
- Update CLI reference (`docs/reference/cli_reference.md`).

---

## Phase 5 — Documentation Pass

**Status:** Not started.

- `docs/explanation/customizing_checks.md`
- `docs/how_tos/customize_palette.md`
- `docs/reference/cli_reference.md`
- Inline docstrings updated throughout earlier phases.

---

## File Impact Summary

| File | Phases |
|------|--------|
| `src/stride/ui/palette.py` | 1, 2 |
| `src/stride/models.py` | 1 |
| `src/stride/project.py` | 1, 2 |
| `src/stride/ui/settings/layout.py` | 1, 3 |
| `src/stride/ui/settings/callbacks.py` | 1, 2, 3 |
| `src/stride/ui/tui.py` | 2, 4 |
| `src/stride/cli/stride.py` | 2, 4 |
| `tests/palette/test_palette.py` | 1, 2 |
| `tests/palette/` (new tests) | 1, 2 |
| `tests/tui/` | 4 |
| `docs/` | 1, 3, 4, 5 |
