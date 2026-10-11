# Bug 0013 — Main result cards show text and controls outside thumbnails

**Status:** Open

## Observed behavior

Document cards show cover art plus visible title, author, badges, tags, star, and Info controls. Bookshelf cards show a mosaic plus a name, count, and action buttons. The main display is not a thumbnail-only grid.

## Reproduction

Open a library with a document and a bookshelf. Compare the visible card contents with the requested thumbnail-only main display.

## Expected behavior

Show only document cover thumbnails and bookshelf mosaic thumbnails in the main result grid. Keep each tile identifiable to assistive technology with a meaningful accessible name. Keep document and bookshelf actions reachable by keyboard and pointer through an Info or detail control that appears on focus or interaction. Preserve source type, page count, title, author, tags, favorite state, and bookshelf details in the detail surface. Distinguish a bookshelf thumbnail visually without exposing private member covers.

## Diagnosis

`static/app.js` builds document captions and controls around `.document-preview`; `static/bookshelves.js` adds visible bookshelf text and action rows. Features 0002 and 0005 require visible card metadata, so their card-level acceptance checks will need revision when this request is implemented.

## Proposed resolution

Make the thumbnail the visible tile surface and move metadata and secondary actions into an accessible detail surface. Provide a visible focus treatment and a touch-friendly way to open details; do not make hover the only route to actions. Keep source-type fallback artwork when a thumbnail is unavailable.

## Verification

**not_run** — Documentation only. Inspect desktop and 390 px layouts in light and dark themes. Check keyboard and touch access to every document and bookshelf action, accessible names, and fallback artwork.
