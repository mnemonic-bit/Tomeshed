# Bug 0014 — Library lacks VDL-style page size and pager controls

**Status:** Open

## Observed behavior

Tomeshed caps each `/api/documents` response at `CATALOG_PAGE_SIZE` (24 by default) and provides a `Load more documents` button. Settings has no page-size preference. VDL offers 5, 10, 20, 50, or Endless scrolling in General Settings and a pager with first, previous, next, and last controls for numbered pages.

## Reproduction

Load more than 24 visible documents. Observe `Load more documents` and no page number or page-size setting. Open General Settings and observe only Theme.

## Expected behavior

Add `Items per page` to General Settings with values 5, 10, 20, 50, and `Endless scrolling`, defaulting to 10 as in VDL. Persist the choice per user. In numbered mode, show page number, page count, matching-item total, and first, previous, next, and last controls beneath the main grid. Disable controls at the boundaries; reset to the first page when search, filters, sort, scope, or page size changes. In endless mode, append authorized result batches automatically and show loading or end-of-results status. Count each bookshelf card as one item in the mixed result set.

## Diagnosis

`templates/index.html` has `loadMoreDocuments` but no pager or page-size setting. `static/app.js` uses offsets and appends on demand. `organization_service.py` caps requested limits at the server setting; `tomeshed.py` preferences store only Theme. VDL's current pager and page-size handling are in `VDL/templates/index.html` and `VDL/static/app.js`.

## Proposed resolution

Extend per-user preferences and validate page-size values on the server. Make the catalog endpoint page the combined authorized result set with a total after search, filters, and sorting. Add numbered pager and endless-scroll behavior in the browser. Retain a server-side maximum request size and handle a page becoming empty after deletion or access changes by moving to the last valid page.

## Verification

**not_run** — Documentation only. Check each page size across reload and restart with two users, mixed document and bookshelf cards, filtered totals, boundary controls, deletion of the last item on a page, and endless loading at desktop and mobile widths.
