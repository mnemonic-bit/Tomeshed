# Bug 0021 — Document Info popover belongs in the reader's left panel

**Status:** Open

## Observed behavior

The three-dot button on each card opens a narrow Info popover under that card. It holds metadata editing, tags, file actions, visibility, removal, and other document details. The reader opens as a separate overlay without those controls. The Info popover is at most 280 px wide.

## Reproduction

Open a document's three-dot Info popover and inspect its controls. Close it, open the document, and observe that the reader has no metadata or action column on the left.

## Expected behavior

Remove the card's three-dot button and Info popover. When a user double-clicks the document thumbnail, open the reader with a left document-side panel containing the current Info metadata and actions, including author, tags, metadata editing, file actions, visibility when authorized, retry indexing when available, removal, and Add to bookshelf. On desktop, target roughly 560 px for the expanded panel, twice the current Info popover's 280 px maximum. Put a minimize button at the panel's top-left corner; minimizing must leave a small restore control and give the reading content the freed space. On a narrow viewport, fit the panel without hiding the reader or its controls. Preserve focus, scroll position, and unsaved form input when minimizing and restoring.

## Diagnosis

`static/app.js` builds `.document-info` inside each card and `static/styles.css` caps its width at 280 px. `templates/index.html` and `static/reader.js` define a reader overlay without a document-side panel. The current Info actions have separate mutation and authorization rules that the new panel must retain.

## Proposed resolution

Build the document-side panel as part of the reader overlay and populate it from the opened document's authorized metadata. Move the existing Info actions and Add to bookshelf into that panel. Refresh the panel after successful mutations and show failures without closing the reader. Keep the reader's page, chapter, zoom, and progress controls usable while the panel is expanded or minimized. Revise feature checks that require the old three-dot Info control.

## Verification

**not_run** — Documentation only. Check every moved field and action for an administrator and a normal user; verify panel width, minimize and restore behavior, form state, reader resizing, keyboard focus, and mobile layout. Confirm failed mutations and document removal produce clear feedback.
