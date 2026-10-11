# Bug 0036 — PDF preview appears to collapse between pages

**Status:** Resolved in `0.4.8`

## Observed behavior

The user reports that the PDF preview flickers when moving to the next page. The preview bubble appears to collapse completely, then reappears with the next page. The report does not establish whether the bubble is briefly hidden or visibly shrinks while the page loads.

## Reproduction

1. Open the preview bubble for a multi-page PDF from its library thumbnail.
2. Select `Next` while keeping the preview open.
3. Watch the bubble between the current page and the next page. The reported symptom is a brief apparent collapse followed by the next page appearing.
4. Repeat across several pages to check whether the effect occurs on every transition or only when a page image has not yet loaded.

## Expected behavior

The preview bubble remains visible and retains a stable frame while the next PDF page loads. The page image and location indicator update when the next page is ready. If consecutive pages have different dimensions, the bubble may resize to fit the new page without collapsing between the two sizes. The preview cursor advances once per `Next` activation, and the reader stays closed.

## Diagnosis

The focused Chromium reproduction changed from a 300 × 500 PDF page to a 600 × 500 page while delaying the second image response. `static/preview.js` replaced the current image with an unloaded image and called `place()`. The measured bubble heights were 613, 113, and 505 pixels: `place()` used the unloaded image's zero height and reduced the bubble to its minimum height before the image load event restored it. Clearing the current image at the start of `load()` also removed the visible page during the request.

## Resolution

Keep the current PDF page and its location indicator visible while the next location and image load. Preload the next image, then replace the current page, update the cursor and controls, and measure the new page in one transition. Ignore image load and error events from requests superseded by navigation or closing the preview.

## Verification

**passed** — `.venv/bin/python tests/browser_check_preview_frame.py` failed before the fix with bubble heights `[613, 613, 113, 505]`. After the fix, the same check exited with code 0 and recorded `[613, 613, 505]` across pages with different dimensions. The bubble remained visible, the location advanced to page 2, and the reader stayed closed.

**passed** — `.venv/bin/python tests/browser_check_preview.py` exited with code 0. Its existing checks cover PDF navigation, reader isolation, focus, stale responses, error handling, and placement.
