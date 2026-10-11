# Bug 0033 — Closing the reader shifts the library scroll position

**Status:** Resolved in `0.4.5`.

## Observed behavior

At a 390 × 300 viewport, `tests/browser_check_reader.py` recorded `window.scrollY` as 416 before a double-click and 363 after closing the reader. The check failed at its scroll restoration assertion.

## Reproduction

1. Run the previous `tests/browser_check_reader.py` check at a 390 × 300 viewport.
2. Observe that `scroll_into_view_if_needed()` records 416, while the first reader close returns to 363.

## Expected behavior

Closing the reader with Close or Escape restores the library search query, the prior scroll position, and focus on the originating card, as required by Feature 0003 AC-01.

## Diagnosis

The card button spans vertical coordinates 52–247 at scroll position 416, while the fixed header extends to coordinate 168. Playwright scrolls the button into a clickable position before its first pointer event. A browser trace recorded `window.scrollY = 363` at the first pointer event, at the double-click event, and at `reader.open` entry. `reader.close` then called `window.scrollTo(0, 363)` and returned focus to the card without moving the page. The test compared the restored position with the earlier staging position of 416, which was no longer the position at reader open.

A separate check dispatched the double-click event at scroll position 416, bypassing Playwright's actionability scroll. Close and Escape each restored 416. This confirms that the reader close path preserves the position recorded at open for this case.

## Resolution

Update `tests/browser_check_reader.py` to capture the library scroll position during the card's double-click event and compare the close result with that position. Add `tests/browser_check_reader_close.py` to move the library page while the reader is open, then verify that Close and Escape each restore the position recorded at open, retain the search query, and return focus to the originating card. No reader source change was needed.

## Verification

**passed** — `.venv/bin/python tests/browser_check_reader.py` exited with code 0 after the assertion captured scroll position 363 at reader open.

**passed** — `.venv/bin/python tests/browser_check_reader_close.py` exited with code 0. Both Close and Escape restored the position recorded at open after the test moved the hidden library page to 0.

**passed** — A temporary browser-only replacement of `window.scrollTo` with a no-op made the focused check fail at Close with `before=390, after=416`. Removing the replacement restored the passing result.

**passed** — The Bug 0030 reviewer served the pre-fix `static/reader.js` in memory and reproduced the original assertion failure. The test baseline error predates the Bug 0030 change.
