# Bug 0029 — Preview position follows reader progress and resets on close

**Status:** Resolved in `0.4.1`

## Observed behavior

A document preview opens at the saved reading position after the document has been opened in the full reader. If the user pages through the preview, moves the pointer to another item, and returns to the document, the preview opens at the saved reading position again. The preview location is lost when the bubble closes.

## Reproduction

1. Open a multi-page PDF in the full reader, navigate to a page after page 1, and close the reader.
2. Hover over that document's thumbnail until its preview opens. Observe that the preview starts at the saved reader page.
3. Use `Previous` or `Next` to display a different preview page.
4. Move the pointer to another item so the preview closes, then hover over the original thumbnail again. Observe that the preview returns to the saved reader page rather than the page displayed in step 3.
5. Repeat with a document that has no saved reading position. Its first preview starts at the beginning, but reopening after preview navigation also returns to the beginning.

## Expected behavior

- The first preview of each document after the library page loads starts at its first PDF page or first EPUB/Docling preview location, regardless of saved reader progress.
- Preview navigation updates a separate preview cursor for that document. If the preview closes and reopens while the library page remains loaded, it resumes at the last location displayed in that document's preview. Switching between documents preserves each document's preview cursor independently.
- Opening or navigating the full reader uses and updates the saved reading position as before. Reader activity does not change an existing preview cursor, and preview activity does not change saved reading position or completion state.
- If the document's preview location count changes, reopen at a valid location within the new count.

## Diagnosis

`preview_service.py`'s `preview_start` reads `reading_positions` and converts the saved reader locator into the first preview index. `static/preview.js` creates each new `active` preview with `index: 0`, calls the unqualified `/preview` endpoint, and discards `active.index` on close. It has no per-document preview cursor beyond the currently open bubble. The reader separately restores saved progress in `static/reader.js`.

At report time, Feature 0004 required the preview to start at the saved reading position in **Opening and navigation** and AC-01. Its **Scope and terms** already defined a browser-state preview cursor separate from saved reading position. The fix revised the start rule and AC-01.

## Resolution

`preview_service.py` now starts at location 0 unless the browser requests an index. It clamps a requested index to the current location count and does not read `reading_positions`. `static/preview.js` keeps the last displayed index for each document in page memory and requests that index when its preview reopens. Feature 0004's start rule and AC-01 now require the same behavior. The reader still restores its saved reading position.

## Verification

**passed** — Before the fix, `PYTHONPATH=. .venv/bin/pytest -q tests/test_preview.py::test_pdf_saved_position_cache_resolution_access_and_progress` failed: `/preview` returned `(page=3, index=2, total=4)` when the check expected `(page=1, index=0, total=4)`.

**passed** — After the fix, `PYTHONPATH=. .venv/bin/pytest -q tests/test_preview.py` reported `7 passed`. The checks cover first preview locations with saved reader progress, reader progress isolation, and clamping after a PDF's page count decreases.

**passed** — `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_preview.py` completed all reported Chromium checks, including independent PDF and EPUB preview cursors, reopening after card switching, and saved reader progress.
