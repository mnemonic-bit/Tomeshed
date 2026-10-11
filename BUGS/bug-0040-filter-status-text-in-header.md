# Bug 0040 — Filter status text occupies the main header

**Status:** Resolved in `0.4.12`

## Observed behavior

The main page header displays `No active filters` below the search controls when no catalog filter is set. When search or filters are active, the same line displays a text summary. The Filters button has a small active dot, but the separate status line still occupies header space and is the primary visible explanation of filter state.

## Reproduction

1. Open the library without a search query or active catalog filter. Observe `No active filters` below the search controls.
2. Set a catalog filter, such as Source type. Observe the summary line and the small dot on the Filters button.
3. Clear the filter. Observe the `No active filters` message return.

## Expected behavior

- Remove the persistent filter status line from the main header, including `No active filters` and the active-filter text summary.
- Give the Filters button a clear visual active state whenever at least one catalog filter is set. The state must be noticeable at a glance in the supported themes and remain visible while the filter popover is closed. Use more than the current small dot if needed to distinguish the active button from the default and hover states.
- Return the Filters button to its default appearance when all catalog filters are cleared. A text search by itself does not activate the filter cue; changing sort order does not activate it either.
- Expose the active state to assistive technology through the button's accessible name or description. Opening the filter popover still shows the selected filter values and its `Clear filters` action.

## Diagnosis

`templates/index.html` rendered `#activeFilters` with the initial `No active filters` text. `static/app.js` updated that text in `catalogFiltersLabel()` and applied `.has-active-filters` when catalog filters were set. `static/styles.css` used that class to reveal a 7 px dot on the Filters button. Feature 0005 required active filters to be displayed in the header.

## Resolution

Removed `#activeFilters` and the dot. `updateFilterButtonState()` gives the Filters button a filled green appearance and the accessible name `Filters active` when a catalog filter is set. Search and sort do not activate the button. A tag matching mode without selected tags leaves the button in its default state; `Clear filters` remains available to reset that mode. Updated Feature 0005 to require the button cue and retained filter values in the popover.

## Verification

**passed** — `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_filter_button_state.py` exited with code 0. The check first failed on the original `#activeFilters` element, then passed after the fix. It checked the absent status line, each catalog filter, multiple filters, search only, sort only, clear, selected values after reopening the popover, the button's accessible name, and computed button styles in light and dark themes. Light and dark screenshots are in `/tmp/tomeshed-bug-0040-browser/`.

**passed** — `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_clear_filters.py`, `tests/browser_check_filters_popover.py`, `tests/browser_check_organization.py`, and `tests/browser_check_bookshelves.py` each exited with code 0 after their status-line expectations were updated to the button state. The checks cover filter clearing, popover placement and focus, combined filters, and bookshelf scope.

**passed** — `node --check static/app.js` and `git diff --check` exited with code 0.
