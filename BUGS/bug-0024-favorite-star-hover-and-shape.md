# Bug 0024 — Favorite star shows a permanent circle and uses text glyphs

**Status:** Resolved in `0.2.21`

## Observed behavior

Every Tomeshed document card shows its Favorite button on a translucent circle with a border and shadow, even when the pointer is elsewhere. The star is a `☆` or `★` text character, so its outline and proportions depend on the browser font. The static circle covers part of the document thumbnail and does not provide a new visual cue when the pointer reaches the button.

## Reproduction

1. Open the library with a document thumbnail in light or dark theme.
2. Inspect the Favorite button before moving the pointer over it. Observe the visible circular background, border, and shadow.
3. Hover the Favorite button. Observe that its background and star color do not change.
4. Mark the document as a favorite and compare the `★` character with VDL's filled SVG star.

## Expected behavior

Match VDL's Favorite control behavior on document cards. At rest, show a legible outlined star for an unselected favorite and a filled star for a selected favorite, without a visible circular button background. On pointer hover, show a dark translucent circular background and change the star to the favorite color, so the control visibly responds. Use one SVG star path for both states; change its fill according to `aria-pressed` instead of switching between font glyphs. Preserve the button's accessible name, `aria-pressed`, pointer target, and visible keyboard focus indicator. The star must remain discoverable and operable without hover on touch devices.

## Diagnosis

VDL defines one star path in `VDL/templates/index.html:189-191`. `VDL/static/app.js:2375-2381` places that SVG in a button with `aria-pressed`. `VDL/static/styles.css:742-779` gives the button a transparent resting background, applies `--favorite-hover-bg` only on hover, and fills the SVG only when pressed. Tomeshed creates text glyphs in `static/app.js:330-334`. Its `.document-star` rules in `static/styles.css:16-18` apply a translucent background, border, and shadow at rest, with no hover-specific state. Bug 0015 improved the opacity and contrast of that permanent circle but did not address when the circle appears or the glyph shape.

## Resolution

`renderDocument` now puts the same SVG star path in every Favorite button. The `aria-pressed` state controls the path fill. The button keeps a 42-pixel pointer target, has no resting circle, border, or button shadow, and gains a dark translucent circle and favorite color on hover. The SVG has a small shadow to keep its outline legible over thumbnails. Light and dark themes retain distinct star colors, and the existing keyboard focus outline remains visible.

## Verification

**passed** — Before the fix, source comparison of the VDL SVG, button markup, and CSS against Tomeshed's document renderer and `.document-star` rules confirmed the difference. VDL is gitignored and excluded from the codebase-memory index, so its current source was read directly.

**passed** — The new SVG assertion in `tests/browser_check_selection.py` failed against the original glyph control. After the fix, `.venv/bin/python tests/browser_check_selection.py` passed. It checks the SVG path and fill, accessible name and pressed state, 42-pixel target, transparent resting state in light and dark themes, hover feedback in both themes, visible keyboard focus outline, and touch activation.

**failed** — `.venv/bin/python tests/browser_check_organization.py` timed out at its later filtered Favorite click: the fixed header intercepted Playwright's pointer action on `book03`. Independent review reproduced the same failure at the same click in a clean `HEAD` archive, before this fix. The focused Favorite checks above passed; the organization check has no result for its later assertions.

**passed** — `node --check static/app.js` and `git diff --check` exited with code 0.
