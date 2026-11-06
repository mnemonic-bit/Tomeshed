# Bug 0047 — Footer counts and uptime do not match the requested display

**Status:** Open

## Observed behavior

The footer shows a count of catalog results rather than the total number of documents and the number of documents matching the current filter. The result count can include bookshelves. The main library view separately shows `N selected` beside the document selection actions. The footer formats uptime as abbreviated days, hours, and minutes, so it does not show seconds or use a single named unit.

## Reproduction

1. Open a library containing documents and at least one bookshelf. Compare the footer count with the number of documents in the library.
2. Apply a document filter or search term that matches fewer documents than the full library. Observe that the footer does not show the matching document count alongside the full document count.
3. Select a document card. Observe the `N selected` text in the main library view.
4. Observe the footer uptime during the first minute of server operation and across a minute or hour boundary. It uses abbreviated units and updates only when the health request completes.

## Expected behavior

- With no filter or search applied, show `NNN Documents` in the footer, where `NNN` is the total number of documents held by the library. Exclude bookshelves and count documents across all catalog pages.
- With a filter or search applied, show `MM Selected of NNN Documents` in the footer. `MM` is the number of documents matching the active query across all pages, including zero matches; `NNN` remains the full document count. In this footer label, `Selected` refers to query matches, not document cards selected for bulk actions. Update the counts after filter, search, import, deletion, or other library changes.
- Remove the visible `N selected` count from the main library selection actions. Keep the selection controls and their behavior.
- Keep the footer's connection and version information alongside the document count and uptime.
- Show uptime as one whole-number unit: `N Seconds` below 60 seconds, `N Minutes` from 60 to 3,599 seconds, `N Hours` from 3,600 to 86,399 seconds, and `N Day` or `N Days` from 86,400 seconds onward. Use the singular form when the displayed value is one. Advance the display as time passes between health checks, including when the unit changes.

## Diagnosis

`static/app.js` writes `/api/documents` response `total` to `#libraryCount`; `organization_service.py` sets `total` to the number of catalog results, including bookshelves, and also returns a separate `library_total` document count. The response does not provide a separate count of documents matching the active query. `templates/index.html` renders `#selectionCount` in the main selection actions. `formatUptime()` in `static/app.js` produces abbreviated days, hours, and minutes and runs when `checkHealth()` receives a response. The VDL blueprint in `VDL/static/app.js` keeps an uptime baseline and refreshes its display every second; its unit selection also includes months and years, while this report requires days for every duration of one day or more.

## Resolution

Pending.

## Verification

**not_run** — This report documents the requested behavior; no UI change or browser check has been performed.
