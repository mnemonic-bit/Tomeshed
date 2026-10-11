# Bug 0008 — Settings Back uses a text arrow instead of the VDL chevron

**Status:** Resolved in `0.2.6`

## Observed behavior

The Settings Back button displays `←` in a bordered square. VDL draws a left-pointing chevron from its `i-chevron` SVG symbol inside a round, transparent button.

## Reproduction

Open Settings in Tomeshed and compare the Back button with the current VDL Settings page at desktop and narrow widths.

## Expected behavior

Use a drawn left-pointing chevron with VDL's button size, hover treatment, and visible keyboard focus. Keep the accessible name `Return to library` and the current Back behavior.

## Diagnosis

`templates/index.html` renders a Unicode arrow. `static/styles.css` gives `.settings-back` a square border. `VDL/templates/index.html` uses `i-chevron`; `VDL/static/styles.css` rotates that symbol 90 degrees for the Settings Back control.

## Resolution

`templates/index.html` now draws the Back chevron with an inline SVG. `static/styles.css` gives the control VDL's 40 px round shape, 20 px icon, transparent resting state, hover treatment, and visible keyboard outline with Tomeshed's theme variables. At narrow widths, Settings starts below the wrapped app header so the control remains visible. The existing `Return to library` name and Back event handler remain in place.

## Verification

**passed** — `.venv/bin/python tests/browser_check_settings_back.py` exited with code 0. The check covered 390 px and 1280 px widths in light and dark themes. For each combination, it verified the SVG and accessible name, 40 px control and 20 px icon, hover state, focus outline, header clearance, and Back activation by Enter and pointer. Screenshots and `checks.json` are in `/tmp/tomeshed-bug-0008-browser/`. Before the code change, the focused check failed because the button lacked an SVG; before the narrow spacing change, the header clearance assertion failed.

**passed** — `.venv/bin/python tests/browser_check.py` exited with code 0, including Settings navigation, theme, viewport, and scrolling checks.
