# Bug 0040 — Filter status text occupies the main header

**Status:** Open

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

`templates/index.html` renders `#activeFilters` with the initial `No active filters` text. `static/app.js` updates that text in `catalogFiltersLabel()` and applies `.has-active-filters` when catalog filters are set. `static/styles.css` uses that class to reveal a 7 px dot on the Filters button. Feature 0005 currently requires active filters to be displayed; its requirement will need to reflect the button cue when this report is resolved.

## Resolution

Pending implementation.

## Verification

**not_run** — This documentation-only report does not change the header. Verify the absence of the status line and the Filters button's active appearance with no filters, each filter type, multiple filters, search only, sort only, and after `Clear filters`. Check the active state in supported themes and through the accessibility tree.
