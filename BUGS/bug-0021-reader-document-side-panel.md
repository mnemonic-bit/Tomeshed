# Bug 0021 — Document Info popover belongs in the reader's left panel

**Status:** Resolved in `0.2.17`

## Observed behavior

The three-dot button on each card opens a narrow Info popover under that card. It holds metadata editing, tags, file actions, visibility, removal, and other document details. The reader opens as a separate overlay without those controls. The Info popover is at most 280 px wide.

## Reproduction

Open a document's three-dot Info popover and inspect its controls. Close it, open the document, and observe that the reader has no metadata or action column on the left.

## Expected behavior

Remove the card's three-dot button and Info popover. When a user double-clicks the document thumbnail, open the reader with a left document-side panel containing the current Info metadata and actions, including author, tags, metadata editing, file actions, visibility when authorized, retry indexing when available, removal, and Add to bookshelf. On desktop, target roughly 560 px for the expanded panel, twice the current Info popover's 280 px maximum. Put a minimize button at the panel's top-left corner; minimizing must leave a small restore control and give the reading content the freed space. On a narrow viewport, fit the panel without hiding the reader or its controls. Preserve focus, scroll position, and unsaved form input when minimizing and restoring.

## Diagnosis

`static/app.js` builds `.document-info` inside each card and `static/styles.css` caps its width at 280 px. `templates/index.html` and `static/reader.js` define a reader overlay without a document-side panel. The current Info actions have separate mutation and authorization rules that the new panel must retain.

## Resolution

The reader now contains a 560 px desktop document panel beside the reading area. On narrow viewports, the panel sits above a visible reading area. The panel contains the former Info metadata and actions, plus `Add to bookshelf`. The card's three-dot control and card-level bookshelf action have been removed. Minimize hides the panel content in place and exposes a restore control, preserving the panel's form values, focus target, and scroll position. Reader open, Mark finished, and Start over update the panel's reading state and last-read values in place without replacing unsaved form input. Successful document mutations refresh the panel; failures appear inside it while the reader stays open. Confirmed removal closes the reader and reports success in the library. The bookshelf chooser can receive focus while opened from the reader.

## Verification

**passed** — `.venv/bin/python tests/browser_check_reader_panel.py` was red before the change on the card Info button and passed after the change. A review check then found stale reading-state fields; the expanded check was red on `unread` after reader open and now passes. It checks open, finish, and start-over fields while preserving form input, focus, and panel scroll; desktop width; administrator and normal-user controls; mobile reader space; minimize and restore state; and failed and successful metadata saves.

**passed** — `.venv/bin/python tests/browser_check_documents.py`, `.venv/bin/python tests/browser_check_organization.py`, `.venv/bin/python tests/browser_check_file_workflows.py`, `.venv/bin/python tests/browser_check_bookshelves.py`, and `.venv/bin/python tests/browser_check_reader.py` pass. These checks cover retry indexing, tags, file export and rename, removal, bookshelf selection, and reader controls.
