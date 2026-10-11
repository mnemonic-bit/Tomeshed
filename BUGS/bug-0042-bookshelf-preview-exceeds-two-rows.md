# Bug 0042 — Bookshelf preview grows beyond two rows

**Status:** Open

## Observed behavior

The bookshelf preview bubble can become too tall when a shelf contains many documents. Its two-column grid expands to show additional rows until the bubble reaches the available viewport height, making the preview larger than a compact four-item overview.

## Reproduction

1. Open a library with a bookshelf containing at least six visible documents.
2. Hover over the bookshelf card until its preview opens.
3. Observe that the bubble grows beyond the height of two thumbnail rows when viewport space allows.

## Expected behavior

- Keep the bookshelf preview grid at two columns. Limit its visible height to two rows of document thumbnails, including their captions and the gap between rows, so the normal preview shows at most a 2 × 2 matrix at once.
- For a shelf with more than four visible documents, keep all documents in shelf order inside the grid and let the user scroll continuously through later rows. Scrolling moves the grid content inside the bubble; it does not grow the bubble or page through fixed groups of four.
- For shelves with one or two rows, let the bubble fit the available content without an unnecessary empty second row. Keep the preview title and dismissal control reachable while the grid scrolls.
- If a narrow or short viewport cannot fit the full two-row height, cap the bubble between the fixed header and footer and allow the grid to scroll within the remaining space. Keep the bubble anchored to the bookshelf card and open while the pointer is over the bubble and its scroll area.
- Support wheel, trackpad, touch, and keyboard scrolling so the rest of the shelf remains reachable.

## Diagnosis

`static/styles.css` already defines `.bookshelf-preview-grid` as a two-column scrollable grid. In `static/bookshelves.js`, `placePreview()` uses the grid's full `scrollHeight` when calculating bubble height and caps the result only at the available viewport height. That allows more than two rows to increase the bubble height on larger screens. Bug 0028 introduced the scrollable full-shelf overview; this report changes only its visible height limit.

## Resolution

Pending implementation.

## Verification

**not_run** — This documentation-only report does not change the preview. Verify the bubble and grid heights with empty, one-row, two-row, and six-or-more-document shelves. For a long shelf, confirm that only two rows fit before scrolling, all later documents remain reachable in order with continuous scrolling, the title and close control stay reachable, and the bubble remains within the viewport at desktop and narrow sizes.
