# Bug 0043 — Reader Remove Document uses an emoji trash can

**Status:** Open

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

Pending implementation.

## Verification

**not_run** — This documentation-only report does not change the icon. Verify the SVG shape in the expanded panel and compact rail in light and dark themes, including hover and keyboard focus. Confirm the accessible name and removal confirmation still work.
