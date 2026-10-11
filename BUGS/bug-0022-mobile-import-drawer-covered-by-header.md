# Bug 0022 — Mobile header covers the import drawer close button

**Status:** Resolved in `0.2.12`

## Observed behavior

At a 390 px viewport, the wrapped fixed header overlaps the top of the import drawer. The header intercepts pointer input intended for `Close imports`, so the drawer cannot be closed with that button.

## Reproduction

Run `.venv/bin/python tests/browser_check_documents.py`. At its mobile import-drawer step, the click on `Close imports` fails because the fixed header receives the pointer event.

## Expected behavior

The import drawer and its close button remain visible and clickable at narrow widths. The header, search controls, and drawer do not overlap in a way that blocks drawer controls. Keyboard activation of `Close imports` also closes the drawer and returns focus to Imports.

## Diagnosis

`static/styles.css` fixes `.app-header` above the drawer with `z-index:80`. At widths up to 700 px, the header wraps beyond the drawer's fixed `top:108px`, while `.imports-drawer` has `z-index:70`. The overlap intercepts clicks on the drawer heading.

## Resolution

`static/app.js` measures the fixed header and version footer with `ResizeObserver` and writes their heights to CSS variables. `static/styles.css` uses those heights for the import drawer's top and bottom edges. The mobile page offset also follows the measured header height, so the library starts below the wrapped header.

## Verification

**passed** — Before the fix, `.venv/bin/python tests/browser_check_documents.py` failed at line 106 because the header intercepted the `Close imports` click. After the fix, the command exited with code 0. The browser check verifies drawer clearance from the header and footer, close-button hit testing, pointer and keyboard activation, and focus return at 390 px and 320 px in light and dark themes. It also verifies clearance after the version footer grows.

**passed** — `.venv/bin/python tests/browser_check_filters_popover.py` and `.venv/bin/python tests/browser_check_settings_back.py` exited with code 0. `git diff --check` and `node --check static/app.js` exited with code 0.
