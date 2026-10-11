# Bug 0023 — Pagination controls appear on single and short result sets

**Status:** Resolved in `0.2.20`

## Observed behavior

In numbered pagination mode, Tomeshed shows the library pager whenever the filtered result total is greater than zero. A one-page result set therefore shows `Page 1 of 1` and four disabled buttons. On two or three pages, Tomeshed still shows the first-page and last-page buttons.

## Reproduction

1. Set **Items per page** to 10 in General Settings.
2. Show 1–10 matching library results. Observe the pager below the grid, including four disabled buttons.
3. Show 11–30 matching results. Observe the first-page and last-page buttons alongside the previous-page and next-page buttons.

The result count includes document and bookshelf cards. Search or filters can produce each result count without changing the library contents.

## Expected behavior

Follow the current VDL pager rule for the selected numbered page size:

| Matching results with page size 10 | Pager | Visible buttons |
| --- | --- | --- |
| 0–10 | Hidden | None |
| 11–30 | Visible | Previous and next |
| 31 or more | Visible | First, previous, next, and last |

For another numbered page size, show the pager only when the matching result total exceeds that size. Show first and last only when the result set spans at least four pages. Keep the current boundary behavior: disable previous and first on page one, and next and last on the final page. Keep the pager hidden in Endless scrolling mode. Recalculate visibility after search, filters, page-size changes, and result mutations.

## Diagnosis

VDL initializes `historyPager` as hidden in `VDL/templates/index.html:290`. Its `fetchHistory` rendering code in `VDL/static/app.js:2987-3004` shows the pager only when numbered mode is active and `historyTotal > historyPageSize`. Within that branch, `maxPage >= 3` controls whether first and last are visible. Tomeshed's `updateCatalogNavigation` in `static/app.js:448-455` instead hides `catalogPager` only for Endless scrolling or zero results and never hides the first and last buttons. `templates/index.html:52-58` defines all four buttons. This is a visibility gap left after Bug 0014 added pagination.

## Resolution

`updateCatalogNavigation` now hides the numbered pager when the matching result total fits on one page. It shows First and Last only when the result set spans at least four pages. Previous and Next remain visible on two or three pages, with the existing boundary disabling rules. The selection browser check now uses Next for its two-page result set.

## Verification

**passed** — Before the fix, source comparison of `VDL/static/app.js:2987-3004`, `VDL/templates/index.html:290-296`, `static/app.js:448-459`, and `templates/index.html:52-58` confirmed the visibility difference. VDL is gitignored and excluded from the codebase-memory index, so its current source was read directly.

**passed** — The new two-page visibility assertion in `tests/browser_check_pagination.py` failed against the original code at line 108. After the fix, `.venv/bin/python tests/browser_check_pagination.py` passed. Its browser checks cover zero and one-page results, two and three-page jump-button visibility, larger result sets, page-size changes, search, filters, result deletion, and Endless scrolling.

**passed** — `.venv/bin/python tests/browser_check_selection.py` passed after its two-page navigation check switched from Last to Next.

**passed** — `node --check static/app.js` and `git diff --check` exited with code 0.
