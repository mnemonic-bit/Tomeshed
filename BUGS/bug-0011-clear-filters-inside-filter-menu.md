# Bug 0011 — Clear Filters is a standalone text button

**Status:** Resolved in `0.2.10`

## Observed behavior

`Clear filters` is a text button in the library tools row. It clears the search query and filter controls, while leaving sorting unchanged.

## Reproduction

Open the library with a search and one filter active. Observe the separate button outside the Filters panel; activate it and observe that the search query also disappears.

## Expected behavior

Put an icon-only Clear Filters action inside the Filters popover. Give it the accessible name `Clear filters`. Activating it clears Type, Author, Favorite, Reading state, Tags, tag-matching mode, and bookshelf scope, then reloads the unfiltered results. Keep the search query and sort choice unchanged. A separate clear control for search may clear search text.

## Diagnosis

`templates/index.html` places `clearFilters` in `.catalog-tools`. Its handler in `static/app.js` also empties `librarySearch`, conflating search text with filter state.

## Resolution

`templates/index.html` places the icon-only `Clear filters` button inside the Filters popover and gives it the accessible name `Clear filters`. `static/app.js` disables the button when no filter is active. Reset clears bookshelf scope, source type, author, favorite, reading state, selected tags, and tag-matching mode. It keeps the search query and sort field and direction, closes the popover, returns focus to the Filters button, and loads the first page of matching results. The active-filter mark excludes search-only state, while the status text still announces the search query.

## Verification

**passed** — `.venv/bin/python tests/browser_check_clear_filters.py` passed placement, accessible name, icon-only content, disabled state with search alone, reset of every filter, preserved search and sort, first-page results, active status, focus return, and tag-matching mode as the only active filter.

**passed** — `.venv/bin/python tests/browser_check_filters_popover.py`, `.venv/bin/python tests/browser_check_organization.py`, and `.venv/bin/python tests/browser_check_bookshelves.py` passed the affected filter, catalog, and bookshelf browser checks.
