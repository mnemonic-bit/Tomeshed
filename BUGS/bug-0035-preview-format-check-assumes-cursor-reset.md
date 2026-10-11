# Bug 0035 — Preview format check assumes the preview cursor resets

**Status:** Resolved in `0.4.7`

## Observed behavior

`tests/browser_check_preview_format.py` times out when it reopens a three-page PDF at a narrow viewport. The check expects the first page's width-to-height ratio, although the preview now retains the third page selected earlier in the same browser page.

## Reproduction

Run `.venv/bin/python tests/browser_check_preview_format.py`. The check times out in `open_preview()` near line 137 while waiting for the first page ratio after reopening the PDF.

## Expected behavior

The format check measures the PDF page displayed after reopening. It verifies that the preview cursor resumes on page 3 and that the bubble uses page 3's ratio at the narrow viewport, while preserving its portrait, landscape, EPUB, and Docling sizing checks.

## Diagnosis

Bug 0029 made preview cursors persist per document for the library page. The format check's final reopen still expects the first page ratio from the older reset behavior.

## Resolution

The final PDF reopen check waits for the retained page 3, verifies its `420 / 842` image ratio, and checks the narrow viewport geometry. The portrait, landscape, EPUB, and Docling checks remain in place.

## Verification

**passed** — `.venv/bin/python tests/browser_check_preview_format.py` exited with code 0 and printed `Bug 0025 browser preview format checks passed`.
