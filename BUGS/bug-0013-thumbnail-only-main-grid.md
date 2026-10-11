# Bug 0013 — Main result cards contain secondary metadata and actions

**Status:** Open

## Observed behavior

Document cards show cover art plus visible title, author, tags, Preview and Add to bookshelf buttons, and Info controls. Bookshelf cards show a mosaic plus a name, count, and action buttons. The main display gives secondary metadata and actions as much space as the cover thumbnails.

## Reproduction

Open a library with a document and a bookshelf. Compare the visible card contents with the requested cover-led main display.

## Expected behavior

Show document cover thumbnails with the document name beneath each cover. Keep bookshelf mosaic thumbnails in the same grid, with accessible names. The document tile may retain the Favorite icon and the New or selected indicator over the cover. Move author, tags, secondary metadata, and document actions into the reader's document-side panel described in Bug 0021. Keep bookshelf actions in an accessible bookshelf detail surface. Distinguish a bookshelf thumbnail visually without exposing private member covers.

## Diagnosis

`static/app.js` builds document captions and controls around `.document-preview`; `static/bookshelves.js` adds visible bookshelf text and action rows. Features 0002 and 0005 require visible card metadata, so their card-level acceptance checks will need revision when this request is implemented. The user's later clarification keeps the document name below its thumbnail; the earlier thumbnail-only wording no longer applies to that name.

## Proposed resolution

Make the thumbnail and document name the visible document tile. Move metadata and secondary actions into the reader's document-side panel. Keep the Favorite and New or selected indicators on the thumbnail as specified in Bugs 0015 and 0020. Provide visible focus and touch-friendly document opening. Keep source-type fallback artwork when a thumbnail is unavailable.

## Verification

**not_run** — Documentation only. Inspect desktop and 390 px layouts in light and dark themes. Check keyboard and touch access to every document and bookshelf action, accessible names, and fallback artwork.
