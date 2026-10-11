# Bug 0015 — Favorite icon background obscures light document covers

**Status:** Resolved in `0.2.13`

## Observed behavior

The Favorite star sits over the upper-right corner of each cover on an opaque surface-colored circle. Many PDF and ebook covers are mostly white, making the circle more prominent than the star.

## Reproduction

Open the library with a mostly white cover and compare the Favorite control over that cover in light and dark themes.

## Expected behavior

Use a more translucent background behind the Favorite icon so the cover remains visible. Keep the star legible in its pressed and unpressed states, with a visible keyboard focus ring and a usable pointer target. The control must still expose its accessible name and `aria-pressed` state.

## Diagnosis

`static/styles.css` sets `.document-star` to `background:var(--surface)`, an opaque theme surface. The control overlaps `.document-art` in `static/app.js`.

## Resolution

`static/styles.css` now gives the Favorite control a 72% opaque overlay matched to each theme. The border and small shadow separate the control from detailed covers. The unpressed and pressed stars use distinct, high-contrast colors in each theme. The pointer target grew from 38 to 42 pixels; the existing 3-pixel keyboard focus ring remains.

## Verification

**passed** — Headless Chromium rendered unpressed and pressed stars over white, dark, and patterned covers in both themes. The screenshots at `/tmp/tomeshed_bug0015_light.png` and `/tmp/tomeshed_bug0015_dark.png` were inspected; cover patterns remain visible through the control, and both star states remain legible. Computed styles confirm alpha `0.72`, a 42-by-42-pixel target, and a 3-pixel solid focus ring. Browser hit testing reaches the button at its center.

**passed** — `.venv/bin/python tests/browser_check_organization.py` exited with code 0, including its Favorite state and rollback checks. The card renderer retains the accessible name and `aria-pressed` state. `git diff --check` exited with code 0.
