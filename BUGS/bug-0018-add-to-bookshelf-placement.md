# Bug 0018 — Add to bookshelf is exposed as a separate card button

**Status:** Open

## Observed behavior

Each document card shows an `Add to bookshelf` button beneath the cover. The button opens the bookshelf chooser.

## Reproduction

Open a library with a document and inspect its card. Activate `Add to bookshelf`; observe the chooser open from the card-level button.

## Expected behavior

Remove `Add to bookshelf` from the visible card. Keep the same chooser available in the document-side panel opened with the reader, as described in Bug 0021. The user first proposed placing this action in the three-dot menu, then requested removal of that menu; the document-side panel is the final destination. Preserve bookshelf ownership and document-access checks.

## Diagnosis

`static/app.js` appends `.document-bookshelf-action` directly to the card and calls `tomeshedBookshelves.choose`. The current three-dot Info control opens a separate card popover, which Bug 0021 removes.

## Proposed resolution

Move the existing chooser trigger into the document-side panel. Keep its current action and error behavior when the panel is collapsed and reopened.

## Verification

**not_run** — Documentation only. Confirm the card has no standalone Add to bookshelf button, the reader panel opens the chooser for the correct document, and unauthorized bookshelf changes remain rejected.
