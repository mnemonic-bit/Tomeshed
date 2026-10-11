# Bug 0008 — Settings Back uses a text arrow instead of the VDL chevron

**Status:** Open

## Observed behavior

The Settings Back button displays `←` in a bordered square. VDL draws a left-pointing chevron from its `i-chevron` SVG symbol inside a round, transparent button.

## Reproduction

Open Settings in Tomeshed and compare the Back button with the current VDL Settings page at desktop and narrow widths.

## Expected behavior

Use a drawn left-pointing chevron with VDL's button size, hover treatment, and visible keyboard focus. Keep the accessible name `Return to library` and the current Back behavior.

## Diagnosis

`templates/index.html` renders a Unicode arrow. `static/styles.css` gives `.settings-back` a square border. `VDL/templates/index.html` uses `i-chevron`; `VDL/static/styles.css` rotates that symbol 90 degrees for the Settings Back control.

## Proposed resolution

Use a small inline SVG chevron and adapt VDL's `.settings-back` styling to Tomeshed's theme variables. Do not depend on a font glyph for arrow shape.

## Verification

**not_run** — Documentation only. Compare light and dark desktop and mobile screenshots with VDL. Activate Back by pointer and keyboard, and inspect its accessible name and focus ring.
