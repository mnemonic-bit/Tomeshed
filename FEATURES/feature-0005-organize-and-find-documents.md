# Organize and find documents

**Source:** User-requested VDL adaptation  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Features 0002 and 0003

## Decision summary

Adapt VDL's tags, favorites, filters, Info panel, and new/view state to a reading library. Keep the primary card grid and the basic title/author search from Feature 0002.

## User experience

- Let users attach reusable tags to a document from its Info panel. Treat tag identity case-insensitively, preserve the first display spelling, and suggest tags already in use.
- Add a favorite star on each thumbnail. Persist it and offer favorite-first ordering without moving a card immediately beneath a user's pointer when its star is clicked.
- Extend search with document type, author, tag (all/any), favorite state, reading state (`unread`, `in progress`, `finished`), and indexed document text. Display the active filters and provide a single clear action.
- A `new` badge means the current user has never opened that document for reading. Hover preview and file download do not clear it. Show the user's last-read date in Info when available.
- Let an authorized user correct title and author metadata without changing the stored original. Show original filename, file size, type, page-count basis, and import time in Info.
- Maintain stable card order during live import updates and filter reconciliation. Reorder on an explicit sort or search action.

## State and search contract

- Store tags and favorites independently of converted content so reconversion does not erase organization.
- Keep each user's reading state separate. Derive `unread`/`in progress`/`finished` from saved reader activity and an explicit finished action; do not equate a thumbnail hover with reading.
- Use Docling-extracted text for full-text search when extraction succeeded. A document without extractable text still matches metadata search. Search results identify matching documents, not arbitrary file paths.
- Authorize metadata edits and tag/favorite mutations on the server. Keep errors visible if a save is rejected.

## Acceptance criteria

- A tag attached to two books appears as one reusable option; removing it from one book leaves the other intact.
- Search and filters combine predictably across title, author, type, tags, favorite, reading state, and available extracted text.
- Favorite state, corrected metadata, and tags survive reloads and restarts; a failed mutation does not leave the card showing a false success.
- Opening a book changes that user's `new` state, while browsing a hover preview does not. Another user's reading state remains independent.

## Boundary

This feature organizes existing catalog records. Source-file ingest/export and personal bookshelves have separate features.
