# Bug 0036 — PDF preview appears to collapse between pages

**Status:** Open

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

Not confirmed. `static/preview.js` changes the preview content to `Loading preview…` in `load()`, replaces that content with the next page image in `render()`, and calls `place()` before and after the image loads. `place()` calculates bubble height from the current content. These are the relevant code paths to inspect with a browser reproduction; source inspection alone does not show which transition produces the reported flicker.

## Resolution

Pending investigation and fix.

## Verification

**not_run** — The symptom was reported by the user. No browser reproduction or regression check was run for this documentation-only report. Verify the fix by paging through a multi-page PDF while observing the bubble's visibility and dimensions before, during, and after each page load, including pages with different aspect ratios.
