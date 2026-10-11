# Bug 0010 — Sorting lacks useful fields and direction controls

**Status:** Resolved in `0.2.9`

## Observed behavior

The library has a text-labeled `Sort` select below the heading with only `Newest first` and `Favorites first`. The catalog API accepts only `newest` and `favorite`; both are descending.

## Reproduction

Open the library and try to order documents by title, author, or type, or reverse the current date order. None is available.

## Expected behavior

Put an icon-only Sort button beside search and Filters. Its compact popover must offer Date added, Title, Author, Type, and Favorite, plus Ascending and Descending for the selected field. Default to Date added, Descending. For Favorite, label the two directions `Favorites first` and `Favorites last`. Display the active sort in the button's accessible name or nearby status. Apply sorting before pagination and use a stable ID tie-breaker. For mixed bookshelf results, sort a bookshelf by its creation date and name; treat its author as missing and place missing authors last in either direction.

## Diagnosis

`templates/index.html` exposes a two-option select. `organization_service.py` validates only `newest` and `favorite`, sorts by import time and ID, then applies favorite-first when requested. The new fields and reverse order require catalog API work as well as UI work.

## Resolution

The search row now has an icon-only Sort button with an accessible name that announces the active field and direction. The keyboard-accessible popover contains Date added, Title, Author, Type, and Favorite fields and both directions. Favorite directions read `Favorites first` and `Favorites last`.

The catalog API accepts `sort=date_added|title|author|type|favorite` and `direction=asc|desc`. Date added defaults to descending. The existing `sort=newest` and `sort=favorite` requests remain valid. The API sorts all authorized documents and bookshelves before pagination. Text comparisons use casefolded values; equal sort keys use ID order. Favorite groups retain date order. Bookshelves use their creation date and name for date sorting, their name for title sorting, and `bookshelf` for type sorting. Bookshelves and documents with no author follow named authors in both directions. A field or direction change resets the visible results to the first page. Favorite changes and live updates preserve the order of visible cards until a sort or search change.

## Verification

**passed** — `PYTHONPATH=. .venv/bin/pytest -q tests/test_catalog_sort.py tests/test_organization.py tests/test_catalog_bookshelves.py` passed 6 tests. The sort tests cover mixed source types and bookshelves, both directions, repeated names, missing authors, stable page boundaries, defaults, aliases, and invalid parameters.

**passed** — `PYTHONPATH=. .venv/bin/python tests/browser_check_organization.py` passed the sort popover, keyboard dismissal, favorite and live update order, and existing organization checks.

**passed** — `PYTHONPATH=. .venv/bin/python tests/browser_check_filters_popover.py` passed filter popover geometry and dismissal checks with the Sort button beside Filters.
