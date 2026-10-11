# Bug 0042 — Bookshelf preview grows beyond two rows

**Status:** Resolved in `0.4.14`

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

`placePreview()` measures the rendered first four tiles after setting the bubble width. It includes the second row's captions, the gap between rows, and grid padding in the visible height. The bubble uses the smaller of that height and the space between the header and footer. Shelves with fewer than four tiles use only their rendered rows; an empty shelf uses the empty message height. Every ordered tile remains in the scrollable grid.

The grid now accepts keyboard focus, with a visible focus outline. Wheel, trackpad, touch, and keyboard input scroll the grid while the bubble remains anchored beside the bookshelf card. The title and Close control stay outside the scroll area.

## Verification

**passed** — `.venv/bin/python tests/browser_check_bookshelf_preview.py` exited with code 0. It checks empty, one-member, two-member, four-member, and 12-member shelves. For the 12-member shelf it checks ordered tiles, a two-column grid, exactly two fully visible rows, a third row below the scroll area, and a bubble no taller than the four-member bubble. Wheel movement of 120 px stops within a row, a second fractional wheel movement scrolls farther, keyboard End and ArrowUp scroll the grid, and touch movement scrolls the mobile grid. The bubble stays open and anchored while scrolling; its title and Close control remain above the grid. A short viewport caps the bubble height, while 180 px and 160 px widths keep it within the viewport.

**passed** — `.venv/bin/python tests/browser_check_bookshelves.py` reported 17 passed checks. `.venv/bin/python tests/browser_check_preview.py` reported 15 passed checks. `node --check static/bookshelves.js` and `git diff --check` exited with code 0.
