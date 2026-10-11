# Bug 0010 — Sorting lacks useful fields and direction controls

**Status:** Open

## Observed behavior

The library has a text-labeled `Sort` select below the heading with only `Newest first` and `Favorites first`. The catalog API accepts only `newest` and `favorite`; both are descending.

## Reproduction

Open the library and try to order documents by title, author, or type, or reverse the current date order. None is available.

## Expected behavior

Put an icon-only Sort button beside search and Filters. Its compact popover must offer Date added, Title, Author, Type, and Favorite, plus Ascending and Descending for the selected field. Default to Date added, Descending. For Favorite, label the two directions `Favorites first` and `Favorites last`. Display the active sort in the button's accessible name or nearby status. Apply sorting before pagination and use a stable ID tie-breaker. For mixed bookshelf results, sort a bookshelf by its creation date and name; treat its author as missing and place missing authors last in either direction.

## Diagnosis

`templates/index.html` exposes a two-option select. `organization_service.py` validates only `newest` and `favorite`, sorts by import time and ID, then applies favorite-first when requested. The new fields and reverse order require catalog API work as well as UI work.

## Proposed resolution

Represent sort as a field and direction in catalog state and API parameters. Define consistent case-insensitive text order, missing-value placement, and stable ties. Reset paging to the first page after an explicit sort change. Keep the current rule that a favorite click or live update does not move cards already visible until the user explicitly sorts or searches again.

## Verification

**not_run** — Documentation only. Use mixed PDF, EPUB, and bookshelf fixtures with repeated names and missing authors. Check both directions, stable page boundaries, the default, and keyboard operation of the popover.
