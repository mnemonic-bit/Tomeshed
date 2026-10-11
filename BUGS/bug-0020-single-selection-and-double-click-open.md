# Bug 0020 — A single click opens the reader instead of selecting a document

**Status:** Open

## Observed behavior

A single click on a document thumbnail opens the reader. The card has no selected state. An unread document displays a `new` badge in its upper-left corner.

## Reproduction

Click a document thumbnail once. Observe the reader open immediately. Close it and inspect the upper-left corner of an unread card; it shows `new` rather than a selection indicator.

## Expected behavior

A single click selects one document without opening the reader. Show a tick on a green background in the selected thumbnail's upper-left corner. If the selected document is New, replace the visible New badge with the tick while selected; restore New when selection is cleared if the document is still unread. Clicking another document moves the single selection. Double-clicking a document thumbnail opens it in the reader. Provide keyboard and touch opening paths, such as Enter on a focused tile and an Open action for a selected touch item. Favorite activation must not select or open the document.

## Diagnosis

`static/app.js` binds the thumbnail button's `click` directly to `tomeshedReader.open`; it renders `.document-new-badge` independently and has no selection state. The reader itself already accepts an opener for focus restoration.

## Proposed resolution

Separate card selection from reader opening, handle double-click without leaving a misleading selected state, and render New and selected indicators from one visual state. Keep selection confined to one document and clear it when the document disappears from the current results.

## Verification

**not_run** — Documentation only. Check one click, another click, double-click, Favorite click, unread badge restoration, keyboard opening, touch opening, and selection after filtering or pagination.
