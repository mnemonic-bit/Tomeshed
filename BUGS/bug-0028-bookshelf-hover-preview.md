# Bug 0028 — Bookshelf cards have no hover preview of their documents

**Status:** Resolved in `0.4.0`

## Observed behavior

Hovering over a bookshelf card's mosaic thumbnail does not open a preview bubble. The card displays at most four cover images. To see the rest of the bookshelf, a user must click the card and open the bookshelf detail dialog, which presents its documents as a list rather than a thumbnail overview.

## Reproduction

1. Add at least five accessible documents to a bookshelf.
2. Hover over a document thumbnail and wait for its preview bubble to open.
3. Hover over the bookshelf's mosaic thumbnail for the same dwell period. Observe that no bookshelf preview opens.
4. Click the bookshelf card. Observe the full detail dialog instead of a scrollable grid of all document thumbnails.

## Expected behavior

- Hovering over a bookshelf mosaic for 800 ms opens a preview bubble anchored beside that bookshelf card, using the same pointer transition behavior as document previews. Preserve the current click action that opens the bookshelf detail dialog.
- Show every document visible to the current user in bookshelf order as a two-column thumbnail grid with as many rows as needed. Keep the preview within the viewport; scroll the grid inside the bubble when the list is taller than the available space. Do not stop at the four covers shown on the bookshelf card.
- Show a clear empty state when the bookshelf has no visible documents. Give a document without a thumbnail a visible fallback tile. Identify each thumbnail by document title for assistive technology, and keep document cover proportions without stretching.
- Keep the preview open while the pointer moves from the card to the bubble and while the user scrolls its grid. Provide a Close control and Escape handling. Make the overview available by keyboard focus and touch through an accessible path consistent with document previews.
- Treat grid entries as overview thumbnails only. They do not need selection, nested document preview, or reader-opening behavior. Include only documents the current user may access, including when a shared bookshelf contains private members.

## Diagnosis

`static/bookshelves.js:28-38` renders a bookshelf mosaic from the card's `covers` array and attaches only a click handler to open the detail dialog. `bookshelf_service.py:120-142` limits that card array to four covers, while `GET /api/bookshelves/<shelf_id>` returns all viewer-visible members in shelf order. `static/preview.js:105-155` opens previews through document-specific URLs and is wired to document cards in `static/app.js:335-340`; bookshelf cards do not register a hover or focus preview. Feature 0007 requires bookshelf covers and counts to include only documents visible to the viewer.

## Resolution

`static/bookshelves.js` now opens a bookshelf preview after an 800 ms mouse or pen hover, an 800 ms keyboard focus dwell, or an 800 ms touch hold. The bubble is anchored beside the card and remains open while the pointer crosses the gap or scrolls its grid. Close and Escape dismiss it; keyboard and touch opening move focus to Close and restore focus to the card on dismissal. A short tap or click still opens the bookshelf detail dialog.

When there is less than 100 px beside the card, placement clamps the bubble inside the viewport and allows it to overlap the card. The pointer bridge still keeps it open during travel into the bubble. The title truncates to leave the Close control visible in narrow viewports.

The preview fetches `GET /api/bookshelves/<shelf_id>` when it opens and renders the response's ordered, viewer-visible `members` as a two-column grid. It includes every member rather than the card's first four covers. Each tile has the document title as its accessible name, uses a 2:3 art area with `object-fit: contain`, and shows a source-type fallback when no thumbnail is available or the image fails. Empty shelves show `No visible documents`. The grid scrolls inside a bubble kept between the app header and footer. Tiles have no selection or reader action. The bookshelf and document previews close each other when the other opens.

## Verification

**passed** — Source inspection confirms that bookshelf cards have no preview handler, their mosaic is limited to four covers, and the bookshelf detail response contains the ordered viewer-visible members needed for a full overview.

**passed** — Before the fix, `.venv/bin/python tests/browser_check_bookshelf_preview.py` failed while waiting for `#bookshelfPreviewBubble`, which did not exist.

**passed** — After the fix, `.venv/bin/python tests/browser_check_bookshelf_preview.py` passed. It checks empty, one-member, and 12-member shelves, ordered titles, six fallback tiles, the two-column scroll grid and cover proportions, viewport bounds on both sides and mobile, pointer travel and scrolling, Close and Escape, keyboard focus, touch hold and short tap, existing detail click, no nested selection or reader action, and a shared shelf that excludes a private member.

**passed** — `.venv/bin/python tests/browser_check_bookshelves.py` reported all 17 checks passed. `.venv/bin/python tests/browser_check_preview.py` reported all 15 checks passed. `.venv/bin/python -m pytest tests/test_bookshelves.py -q` reported 8 passed. `node --check static/bookshelves.js`, `node --check static/preview.js`, and `git diff --check` exited with code 0.

**passed** — Review follow-up: the focused browser check failed at 180 px with bubble bounds x=87..187, beyond the 180 px viewport. After placement was clamped, `.venv/bin/python tests/browser_check_bookshelf_preview.py` passed at both 180 px and 160 px widths. It checks horizontal bounds, header and footer bounds, the Close control's bounds, and pointer travel into the bubble. `node --check static/bookshelves.js` and `git diff --check` exited with code 0. `VERSION` remains `0.4.0` for this correction to the Bug 0028 implementation.
