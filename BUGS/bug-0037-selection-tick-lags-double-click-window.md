# Bug 0037 — Selection tick appears after the double-click window

**Status:** Resolved in `0.4.9`

## Observed behavior

The user reports that a single click on a document thumbnail does not show the selection tick until after the interval in which a second click would be recognized as a double-click. This leaves a period in which the click can no longer open the reader as a double-click, but the library still gives no visible selection feedback.

## Reproduction

1. Open the library with an unselected document thumbnail.
2. Click the thumbnail once with a mouse or pen.
3. Observe when the selection tick appears in the thumbnail's upper-left corner.
4. Compare that delay with the longest interval at which two clicks on the same thumbnail still open the reader as a double-click in the same browser and input environment. The reported behavior is that the tick appears later.

## Expected behavior

Show the selection tick as soon as the opportunity for the second click to form a double-click has expired. The app's single-click selection delay and effective double-click recognition interval should end together, without an additional period of missing feedback. A recognized double-click still opens the reader without briefly showing the tick or changing the selected count. Keyboard and touch selection retain their immediate feedback.

If the effective double-click interval varies by browser or system settings, choose and document a click handling rule that gives the earliest reliable selection feedback for each supported environment. Verify the boundary with clicks just inside and just outside the interval.

## Diagnosis

`static/app.js` waited 500 ms after a mouse or pen `click` before showing selection. The browser check had no shorter selection deadline, so its first-click selection remained invisible for the full 500 ms. Separate Playwright pointer clicks 105 ms apart generated two `click` events with `detail = 1` and no `dblclick`; Playwright supplies Chromium's click count through the browser automation protocol. That protocol cannot measure the operating system's native double-click interval. Page JavaScript also has no API for reading that interval, so the app cannot promise to match a browser or system setting that differs from its own rule.

## Resolution

`static/app.js` now uses one 300 ms interval, measured from the first mouse or pen `click` to the second `pointerdown`, for both selection commitment and reader opening. A second pointer press within that interval pauses the selection timer while its `click` is resolved. A document-level release listener commits the first selection if the second press ends outside the thumbnail or is canceled. If the second click has `detail > 1`, the reader opens without changing selection. At or after the interval, the first click selects the document. A later browser `dblclick` does not open the reader; its second click is treated as a new single click. This app-defined interval gives the earliest reliable selection feedback under the app's double-click rule on every browser, although a system configured with a longer double-click interval may report a `dblclick` that the app treats as two single clicks. Keyboard and touch selection still apply immediately.

`tests/browser_check_reader_close.py` and `tests/browser_check_preview.py` now send pointer double-clicks rather than dispatching a `dblclick` event without clicks. Their original reader and preview assertions remain in place.

## Verification

**passed** — Before the fix, `.venv/bin/python tests/browser_check_double_click.py` timed out waiting for selection within 400 ms. After the fix, the same check passed. It records `pointerdown`, `click`, `dblclick`, and selection mutation times. A second mouse or pen press about 200 ms after the first click opens the reader with no selection mutation. A lone click shows the tick within 450 ms after the click. A browser `dblclick` sent after that tick leaves the reader closed. The check also confirms immediate touch selection and the existing keyboard behavior.

**passed** — Independent review found that releasing a second press outside the thumbnail left selection pending. The added browser case failed before the release listener was added: its first click remained unselected after the second press moved off the thumbnail and released. It passed after the release listener was added.

**passed** — `.venv/bin/python tests/browser_check_selection.py`, `.venv/bin/python tests/browser_check_preview.py`, and `.venv/bin/python tests/browser_check_reader_close.py` exited with code 0. `node --check static/app.js` exited with code 0.
