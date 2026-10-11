# Bug 0012 — Bookshelves are isolated above document results

**Status:** Open

## Observed behavior

The library renders `My bookshelves` and `Shared with me` as separate lists above the document grid. Bookshelves do not participate in search, sorting, or document pagination.

## Reproduction

Create one owned bookshelf and receive one shared bookshelf. Open the library with documents present; observe two bookshelf sections above the document results. Search for a bookshelf name and observe that document search does not find that bookshelf.

## Expected behavior

Show accessible owned and shared bookshelves as cards in the same main result grid as documents, with no separate bookshelf list. The Filters popover must offer a scope choice: `All`, `Documents only`, and `Only bookshelves`. Default to `All`. Search must match bookshelf names and document fields, and scope must combine with search. `Only bookshelves` must include owned and shared bookshelves the user may access. Keep bookshelf ownership and sharing actions available through the bookshelf card's detail controls. Never reveal a private member through a shared bookshelf's preview or search result.

## Diagnosis

`templates/index.html` has a separate `bookshelfArea`, `static/bookshelves.js` renders its own lists, and `organization_service.py` paginates documents alone. Feature 0007 explicitly specified separate sections and excluded bookshelf cards from page slots; its library-view and AC-04 text will need revision for this request.

## Proposed resolution

Build one authorized result model for document and bookshelf cards. Apply search, scope, sorting, and total-count calculation before pagination. Keep the existing bookshelf detail and sharing authorization rules. Use the Filters popover as the primary scope control. As a later search convenience, `shelf:yes` and `shelf:no` may map to the same scope state, following VDL's `playlists:yes` syntax; if added, parse them as operators rather than literal document text and show the interpreted scope in the UI.

## Verification

**not_run** — Documentation only. Check mixed, document-only, and bookshelf-only results with two users, private members, search matches, and more items than one page. Confirm no duplicate bookshelf section and no access leak.
