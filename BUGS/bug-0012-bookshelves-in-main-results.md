# Bug 0012 — Bookshelves are isolated above document results

**Status:** Resolved in `0.2.8`

## Observed behavior

The library renders `My bookshelves` and `Shared with me` as separate lists above the document grid. Bookshelves do not participate in search, sorting, or document pagination.

## Reproduction

Create one owned bookshelf and receive one shared bookshelf. Open the library with documents present; observe two bookshelf sections above the document results. Search for a bookshelf name and observe that document search does not find that bookshelf.

## Expected behavior

Show accessible owned and shared bookshelves as cards in the same main result grid as documents, with no separate bookshelf list. The Filters popover must offer a scope choice: `All`, `Documents only`, and `Only bookshelves`. Default to `All`. Search must match bookshelf names and document fields, and scope must combine with search. `Only bookshelves` must include owned and shared bookshelves the user may access. Keep bookshelf ownership and sharing actions available through the bookshelf card's detail controls. Never reveal a private member through a shared bookshelf's preview or search result.

## Diagnosis

`templates/index.html` has a separate `bookshelfArea`, `static/bookshelves.js` renders its own lists, and `organization_service.py` paginates documents alone. Feature 0007 explicitly specified separate sections and excluded bookshelf cards from page slots; its library-view and AC-04 text will need revision for this request.

## Resolution

`/api/documents` now returns authorized document and bookshelf items in one sorted result page. The catalog applies search, scope, document filters, sorting, and total-count calculation before pagination. Bookshelf previews use the existing viewer-specific detail projection, so private members are omitted from shared counts and covers. The browser renders both item types in the main grid and offers `All`, `Documents only`, and `Only bookshelves` in the Filters popover. The separate bookshelf lists were removed. An owned bookshelf's detail dialog shows `Arrange bookshelves` in saved position order with keyboard-accessible move controls; shared recipients do not see that manager. The mixed grid continues to follow catalog sorting after a move. Editing, sharing, and reading remain available through the bookshelf detail dialog.

## Verification

**passed** — `.venv/bin/python -m pytest -q` completed with 65 passed, including mixed pages, owned and shared shelves, scope, search, sort order, and private member omission. `.venv/bin/python tests/browser_check_bookshelves.py` passed its 17 browser checks, including the owner's saved arrangement before and after reload, a keyboard move, a shared recipient without arrangement controls, and unchanged grid sort. `.venv/bin/python tests/browser_check_organization.py` and `.venv/bin/python tests/browser_check_filters_popover.py` passed their catalog and filter checks. `node --check static/app.js` and `node --check static/bookshelves.js` exited with code 0.
