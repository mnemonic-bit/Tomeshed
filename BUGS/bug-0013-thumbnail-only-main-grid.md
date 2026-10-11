# Bug 0013 — Main result cards contain secondary metadata and actions

**Status:** Resolved in `0.2.18`

## Observed behavior

Document cards show cover art plus visible title, author, tags, Preview and Add to bookshelf buttons, and Info controls. Bookshelf cards show a mosaic plus a name, count, and action buttons. The main display gives secondary metadata and actions as much space as the cover thumbnails.

## Reproduction

Open a library with a document and a bookshelf. Compare the visible card contents with the requested cover-led main display.

## Expected behavior

Show document cover thumbnails with the document name beneath each cover. Keep bookshelf mosaic thumbnails in the same grid, with accessible names. The document tile may retain the Favorite icon and the New or selected indicator over the cover. Move author, tags, secondary metadata, and document actions into the reader's document-side panel described in Bug 0021. Keep bookshelf actions in an accessible bookshelf detail surface. Distinguish a bookshelf thumbnail visually without exposing private member covers.

## Diagnosis

`static/app.js` builds document captions and controls around `.document-preview`; `static/bookshelves.js` adds visible bookshelf text and action rows. Features 0002 and 0005 require visible card metadata, so their card-level acceptance checks will need revision when this request is implemented. The user's later clarification keeps the document name below its thumbnail; the earlier thumbnail-only wording no longer applies to that name.

## Resolution

Document tiles now show the cover and title, with Favorite, New or selected state, and an accessible indexing-warning indicator over the cover. Source type, page count, author, tags, and document actions are available in the reader document panel. Bookshelf tiles show the mosaic, a Bookshelf marker, and the name; their accessible names include the visible-member count. The bookshelf detail retains the count, Continue reading, editing, and deletion actions. The catalog renders only authorized cover IDs supplied by the bookshelf API. Features 0002, 0005, and 0007 now describe these locations.

## Verification

**passed** — Before the fix, `PYTHONPATH=. .venv/bin/python tests/browser_check_organization.py` failed because document cards contained author and tags, and `PYTHONPATH=. .venv/bin/python tests/browser_check_bookshelves.py` failed because bookshelf cards contained an action row. Both checks passed after the fix. `tests/browser_check_documents.py` passed with 390 px and 1280 px light and dark screenshots, reader count checks, fallback artwork, accessible warning, keyboard opening, and touch selection and opening. `tests/browser_check_bookshelves.py` passed with 390 px light and dark screenshots, keyboard and touch opening, detail actions, accessible count, and private-cover filtering. `tests/browser_check_selection.py`, `tests/browser_check_preview.py`, `tests/browser_check_reader_panel.py`, and `tests/browser_check_pagination.py` passed. `PYTHONPATH=. .venv/bin/pytest -q` passed with 70 tests. Screenshots are under `/tmp/tomeshed-feature-0002-browser/` and `/tmp/tomeshed-feature-0007-browser/`.
