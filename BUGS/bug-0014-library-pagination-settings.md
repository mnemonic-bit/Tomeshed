# Bug 0014 — Library lacks VDL-style page size and pager controls

**Status:** Resolved in `0.2.11`

## Observed behavior

Tomeshed caps each `/api/documents` response at `CATALOG_PAGE_SIZE` (24 by default) and provides a `Load more documents` button. Settings has no page-size preference. VDL offers 5, 10, 20, 50, or Endless scrolling in General Settings and a pager with first, previous, next, and last controls for numbered pages.

## Reproduction

Load more than 24 visible documents. Observe `Load more documents` and no page number or page-size setting. Open General Settings and observe only Theme.

## Expected behavior

Add `Items per page` to General Settings with values 5, 10, 20, 50, and `Endless scrolling`, defaulting to 10 as in VDL. Persist the choice per user. In numbered mode, show page number, page count, matching-item total, and first, previous, next, and last controls beneath the main grid. Disable controls at the boundaries; reset to the first page when search, filters, sort, scope, or page size changes. In endless mode, append authorized result batches automatically and show loading or end-of-results status. Count each bookshelf card as one item in the mixed result set.

## Diagnosis

`templates/index.html` has `loadMoreDocuments` but no pager or page-size setting. `static/app.js` uses offsets and appends on demand. `organization_service.py` caps requested limits at the server setting; `tomeshed.py` preferences store only Theme. VDL's current pager and page-size handling are in `VDL/templates/index.html` and `VDL/static/app.js`.

## Resolution

`tomeshed.py` now migrates existing preferences and persists a validated per-user `page_size` value. Theme-only and page-size-only updates preserve the other setting. The default catalog request cap is 50; the existing endpoint continues to page the authorized mixed result set and report its filtered total. General Settings offers 5, 10, 20, 50, and Endless scrolling. Numbered mode shows the current page, total pages, matching-item count, and boundary-disabled navigation. Search, filter, sort, scope, and page-size changes return to page one. A shortened final page moves to the last valid page. Endless mode fetches authorized batches when the grid sentinel enters the viewport, including when the sentinel is already visible after returning from Settings, and reports loading and completion. Live refreshes retain visible card order under Favorite sorting.

## Verification

**passed** — `PYTHONPATH=. .venv/bin/pytest -q` (70 tests), `node --check static/app.js`, and `git diff --check` exited with code 0. `tests/test_catalog_pagination.py` covers value validation, two-user isolation, mixed authorized totals, 50-item requests, and persistence after reinitialization. `tests/test_app.py` covers migration from the earlier preferences schema.

**passed** — `.venv/bin/python tests/browser_check_pagination.py` exercised each page size, mixed bookshelf and document results, pager boundaries, search/scope/sort resets, deletion of the only item on the last page, endless loading at desktop and mobile widths, two users, and persistence after process restart. `.venv/bin/python tests/browser_check_clear_filters.py`, `.venv/bin/python tests/browser_check_bookshelves.py`, and `.venv/bin/python tests/browser_check_organization.py` exited with code 0 after replacing their Load more expectations. The organization check retained its sort, favorite-order, and concurrent live-update assertions while using endless scrolling.

**failed, separate defect** — `tests/browser_check_documents.py` reaches a mobile import-drawer close button that the header intercepts. The mobile drawer overlap is outside Bug 0014 and is assigned to Bug 0022.
