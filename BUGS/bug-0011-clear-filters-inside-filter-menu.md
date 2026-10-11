# Bug 0011 — Clear Filters is a standalone text button

**Status:** Open

## Observed behavior

`Clear filters` is a text button in the library tools row. It clears the search query and filter controls, while leaving sorting unchanged.

## Reproduction

Open the library with a search and one filter active. Observe the separate button outside the Filters panel; activate it and observe that the search query also disappears.

## Expected behavior

Put an icon-only Clear Filters action inside the Filters popover. Give it the accessible name `Clear filters`. Activating it clears Type, Author, Favorite, Reading state, Tags, tag-matching mode, and bookshelf scope, then reloads the unfiltered results. Keep the search query and sort choice unchanged. A separate clear control for search may clear search text.

## Diagnosis

`templates/index.html` places `clearFilters` in `.catalog-tools`. Its handler in `static/app.js` also empties `librarySearch`, conflating search text with filter state.

## Proposed resolution

Move the action into the filter panel and separate filter reset from search reset. Hide or disable it when no filter is active, while keeping the active-filter indication accurate.

## Verification

**not_run** — Documentation only. Set search, every filter, and a nondefault sort; clear filters and confirm the query and sort remain, all filter values reset, and results and page position update.
