# Bug 0020 — A single click opens the reader instead of selecting a document

**Status:** Resolved in `0.2.16`

## Observed behavior

A single click on a document thumbnail opens the reader. The card has no selected state. An unread document displays a `new` badge in its upper-left corner.

## Reproduction

Click a document thumbnail once. Observe the reader open immediately. Close it and inspect the upper-left corner of an unread card; it shows `new` rather than a selection indicator.

## Expected behavior

A single click selects one document without opening the reader. Show a tick on a green background in the selected thumbnail's upper-left corner. If the selected document is New, replace the visible New badge with the tick while selected; restore New when selection is cleared if the document is still unread. Clicking another document moves the single selection. Double-clicking a document thumbnail opens it in the reader. Provide keyboard and touch opening paths, such as Enter on a focused tile and an Open action for a selected touch item. Favorite activation must not select or open the document.

## Diagnosis

`static/app.js` binds the thumbnail button's `click` directly to `tomeshedReader.open`; it renders `.document-new-badge` independently and has no selection state. The reader itself already accepts an opener for focus restoration.

## Resolution

`static/app.js` now tracks one selected document. A thumbnail click selects or deselects the document; a second document click moves selection. The selected card shows a green tick in place of New and exposes an Open action for touch. A thumbnail double-click or focused thumbnail Enter opens the reader and clears selection. Favorite activation does not change selection. Catalog replacement clears selection when its document leaves the current results.

## Verification

**passed** — `PYTHONPATH=tests:. .venv/bin/python tests/browser_check_selection.py` reproduced the one-click reader open before the fix and passed after the fix. The check covers single selection, moving and clearing selection, New restoration, Favorite isolation, double-click, Enter, touch Open, filtering, and pagination. `tests/browser_check_preview.py` passed, including touch hold without selection; `tests/browser_check_reader.py`, `tests/browser_check_organization.py`, and `tests/browser_check_documents.py` passed after updating their reader-opening actions.
