# Bug 0002 — Preview browser check scrolled the preview instead of the page

**Status:** Resolved in `0.2.0`

## Observed behavior

`./tests/run-all.sh` reached `tests/browser_check_preview.py` and timed out at the `scroll_origin_offscreen` check. A direct rerun of `tests/browser_check_preview.py` repeated the timeout at line 253. The previous `page.mouse.wheel(0, 600)` did not move the first card's preview trigger above the fixed header.

## Reproduction

Run `.venv/bin/python tests/browser_check_preview.py` with Playwright Chromium. The failure occurs after the narrow viewport edge-placement checks when the script opens a preview and sends a wheel event while the pointer is over the preview trigger or bubble.

## Expected behavior

The check must scroll the document page until the preview trigger is above the fixed header, then observe that the preview closes. Scrolling the bubble's own content does not establish that condition.

## Diagnosis

The wheel event targets the pointer location, which can be over the preview bubble's scrollable content. The fixed 600-pixel amount also does not derive from the trigger's actual position. The repeated timeout and the preview bubble's `overflow:auto` style support this diagnosis.

## Resolution

`tests/browser_check_preview.py` now computes the trigger's distance from the fixed header and calls `window.scrollBy` on the page. The test still waits for the trigger to leave the visible page area and for the preview bubble to close.

## Verification

`.venv/bin/python tests/browser_check_preview.py` exited with code 0 after this change. Its report includes `"scroll_origin_offscreen": "passed"`. The complete `./tests/run-all.sh` gate then exited with code 0: 64 Python tests, all seven browser scripts, both platform lock checks, and the isolated shipping-image smoke passed.
