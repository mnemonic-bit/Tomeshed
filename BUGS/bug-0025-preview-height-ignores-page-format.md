# Bug 0025 — Preview height ignores the displayed page format

**Status:** Resolved in `0.2.22`

## Observed behavior

The document preview bubble uses a height capped at 500 px regardless of the displayed PDF page. An A4 portrait page is substantially taller than it is wide, so the preview window does not follow the page's proportions. Portrait, landscape, and other page sizes receive the same height when viewport space permits.

## Reproduction

1. Add a PDF with an A4 portrait page and open its library card preview at a desktop viewport.
2. Compare the preview bubble's width and height with the displayed page's width and height. Observe that the bubble height is capped at 500 px rather than derived from the A4 ratio.
3. Preview a landscape PDF page, or move between differently sized pages in one PDF. Observe that the bubble height does not follow the current page format.

## Expected behavior

Keep the preview bubble's current width selection: use its normal width when horizontal space allows, and reduce width only when needed to fit beside the card. For a PDF page, set the preview content area's target height from the current page's width-to-height ratio, then add the toolbar, controls, padding, and borders to obtain the bubble height. Recalculate the height when a different PDF page is shown, including when page orientation changes. The page image must retain its aspect ratio without stretching or cropping.

Keep the entire bubble between the fixed header and footer. If the page-based height exceeds that available space, cap the bubble height and allow the page content to scroll inside it while keeping the preview controls reachable. For EPUB and DoclingDocument JSON excerpts, which do not have a physical page format, size the bubble to its content within the same viewport bounds rather than applying a PDF page ratio.

## Diagnosis

`static/preview.js:48-74` computes a width of up to 495 px from horizontal space, then assigns a height of up to 500 px from viewport space. That calculation does not inspect the current page. `static/preview.js:83-104` inserts the page image and calls `place()` without waiting for its dimensions. `preview_service.py:369-392` obtains each source PDF page's width and height and renders a PNG with the same aspect ratio, but the preview location response supplies an image URL rather than page dimensions. `.preview-content` in `static/styles.css:29` can scroll internally, so the fixed bubble height can obscure the page's full portrait proportions. The viewport bounds in Feature 0004 still apply.

## Resolution

`place()` now measures the displayed preview content at the selected bubble width. It adds the toolbar, controls, margins, padding, and border height, then caps the bubble at the space between the fixed header and footer. The PDF image triggers placement again after loading, so page navigation recalculates the height from the displayed page ratio. EPUB and DoclingDocument JSON excerpts use their rendered content height; excerpt images also trigger placement after loading. Content scrolls within a capped bubble while the controls remain visible.

## Verification

**passed** — Before the fix, source inspection confirmed the fixed 500 px height cap in `static/preview.js`, the preserved PDF image ratio in `preview_service.py`, and the scrollable preview content area in `static/styles.css`.

**passed** — `tests/browser_check_preview_format.py` failed before the fix because the portrait A4 image was about 669 px tall inside a 390 px content area. After the fix, `.venv/bin/python tests/browser_check_preview_format.py` passed. It checks portrait A4, landscape A4, a third tall page in the same PDF, image aspect ratio, EPUB and DoclingDocument JSON excerpts, and a narrow viewport with internal scrolling and reachable controls.

**passed** — `.venv/bin/python tests/browser_check_preview.py` passed all 15 existing preview checks. Its pointer-leave check now moves the pointer outside the card and bubble after moving keyboard focus away from preview controls; the old test point could fall inside the pointer bridge when the bubble height changed.

**passed** — `node --check static/preview.js` and `git diff --check` exited with code 0.
