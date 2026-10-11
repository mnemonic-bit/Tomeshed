# Bug 0043 — Reader Remove Document uses an emoji trash can

**Status:** Resolved in `0.4.15`

## Observed behavior

The `Remove document` action in the full-document reader's left panel uses a trash-can emoji. Its appearance varies by platform and does not match the outlined trash icon used by the VDL blueprint.

## Reproduction

1. Open a document in the full reader.
2. Expand the left document panel and inspect the `Remove document` action near the bottom.
3. Minimize the panel and inspect the same action in the compact rail.
4. Compare both icons with VDL's trash icon in `VDL/templates/index.html` (`i-trash`).

## Expected behavior

Use the shape of VDL's `i-trash` SVG symbol for `Remove document` in both the expanded panel and compact rail. Render the icon as a consistent vector that follows Tomeshed's existing danger color and fits the current control sizes. Keep the accessible name `Remove document`, the confirmation step, and the removal behavior.

## Diagnosis

`static/app.js` passes the `🗑` character to the shared `action()` helper for both reader controls, and the helper renders that character in `.document-action-icon`. VDL defines `i-trash` as an outlined 16 × 16 SVG in `VDL/templates/index.html` and uses it for destructive actions in `VDL/static/app.js`. The replacement belongs in Tomeshed's files; VDL is a read-only reference.

## Resolution

`static/app.js` now builds the VDL `i-trash` outline as an SVG for both `Remove document` controls. `static/styles.css` sizes the icon to 20 × 20 px within the existing 44 px controls and gives the controls a theme-aware hover background. The SVG uses `currentColor`, so the existing danger color applies in light and dark themes. The button's accessible name, confirmation, and deletion callback remain in place.

## Verification

**passed** — `.venv/bin/python tests/browser_check_reader_panel.py` exited with code 0. The browser check compares both SVG path sets with VDL's `i-trash`, checks the 20 px icon and 44 px compact control, and checks the danger color, hover background, and visible keyboard focus in light and dark themes in both panel states. It checks the `Remove document` accessible name, dismisses confirmation from each panel state without deleting the document, then accepts confirmation and verifies that a different document is removed.

**passed** — `node --check static/app.js` and `git diff --check` exited with code 0.
