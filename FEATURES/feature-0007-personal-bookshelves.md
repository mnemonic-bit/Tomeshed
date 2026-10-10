# Add personal bookshelves

**Source:** User-requested VDL adaptation  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Features 0002 and 0003

## Decision summary

Translate VDL playlists into ordered bookshelves. A shelf gathers documents for a reading purpose and offers a stable way to continue a book, while each book's actual reading position remains attached to the user and document.

## User experience

- Let a signed-in user create, rename, reorder, and remove personal shelves; add or remove books from a shelf without deleting the documents themselves.
- Show shelves as a distinct section in the library and expose quick-add from a document card. A shelf view shows its ordered books with cover, title, type, and the user's reading state.
- `Continue reading` opens the last active book on that shelf at the user's saved position. Opening a different book does not reset progress in the others.
- Give shelves private-by-default visibility. The owner may share a shelf read-only with named users. Recipients see only shelf items they are otherwise authorized to open. Only the owner can edit shelf membership and order.
- Keep catalog documents shared with signed-in users by default, as in VDL, but allow an owner to mark a document private. Apply document visibility to cards, search, reader, previews, exports, and shelves. A shelf share never overrides document visibility.
- When a document is removed from the catalog, remove its shelf membership and keep the shelf order and other books intact.

## Persistence and acceptance criteria

- Store shelf ownership, ordered membership, and last active document in SQLite. Preserve them across restarts and concurrent browser sessions.
- A user can create a shelf, add two books, reorder them, resume one book, and return later to the same page or EPUB location.
- Removing a book from a shelf leaves the underlying document and saved reading position unchanged. Removing the document removes it from every shelf.
- API access to shelves enforces ownership or an explicit share, and a shared shelf never discloses a document the viewer cannot otherwise open. Private documents are absent from unauthorized search and file responses.

## Boundary

Continuous playback, shuffle, and automatic advancement from one book to another are not reading-library defaults.
