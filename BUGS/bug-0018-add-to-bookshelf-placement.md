# Bug 0018 — Add to bookshelf is exposed as a separate card button

**Status:** Resolved in `0.2.17`

## Observed behavior

Each document card shows an `Add to bookshelf` button beneath the cover. The button opens the bookshelf chooser.

## Reproduction

Open a library with a document and inspect its card. Activate `Add to bookshelf`; observe the chooser open from the card-level button.

## Expected behavior

Remove `Add to bookshelf` from the visible card. Keep the same chooser available in the document-side panel opened with the reader, as described in Bug 0021. The user first proposed placing this action in the three-dot menu, then requested removal of that menu; the document-side panel is the final destination. Preserve bookshelf ownership and document-access checks.

## Diagnosis

`static/app.js` appends `.document-bookshelf-action` directly to the card and calls `tomeshedBookshelves.choose`. The current three-dot Info control opens a separate card popover, which Bug 0021 removes.

## Resolution

Bug 0021 moved `Add to bookshelf` from each document card into the reader's document-side panel. The panel renders the action for the current document, and the action calls the existing bookshelf chooser. Minimizing the panel hides it without replacing its content; restoring the panel makes the action available again. The chooser lists only the user's owned bookshelves. The bookshelf membership API still checks bookshelf ownership, document access, and ready state before adding a member.

## Verification

**passed** — Source inspection of `static/app.js` and `static/reader.js` found no card-level bookshelf action. `renderDocumentInfo` adds the action to the reader panel for the document passed to `tomeshedReader.open`, and minimizing and restoring the panel preserves its content.

**passed** — `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_reader_panel.py` passed. The browser check found the action in the panel and verified that the panel and its contents survive minimize and restore.

**passed** — `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_bookshelves.py` passed. The browser check opened `PDF Book`, used the panel action to add it to `Reading`, and found `PDF Book` as the shelf's sole member.

**passed** — `PYTHONPATH=. .venv/bin/pytest -q tests/test_bookshelves.py -k share_authorization_filtering_and_revocation` passed. The API test checks that a recipient cannot change the owner's bookshelf and cannot add an inaccessible document to a bookshelf they own.
