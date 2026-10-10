# Organize and find documents

**Source:** User-requested VDL adaptation  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Features 0002 and 0003

## Outcome

Let a signed-in user organize catalog documents with tags and favorites, correct displayed metadata, and narrow the library by document attributes, reading state, and extracted text. Keep each user's reading state separate while making document tags, favorites, and corrected metadata available to users who can access the document.

## Scope and terms

- Use **document** and its stable document ID as defined in Feature 0002. Apply this feature to documents with import state `ready` or `ready_with_warning`.
- Use **tag** for a reusable label attached to a document. Tags belong to catalog documents, not to users or Docling output.
- Use **favorite** for a boolean value attached to a document. A favorite belongs to the shared catalog record, not to an individual user.
- Use **reading state** for one user's state on one document: `unread`, `in progress`, or `finished`. Derive it from reader-open and completion records rather than storing a second editable status.
- Keep the source file, import pipeline, and basic title, author, and original-filename search from Feature 0002. Use Feature 0003's reader and completion actions. Feature 0007 adds document visibility rules.

## Organization and metadata

- Let any active signed-in user who may open a document add and remove its tags in the Info menu.
- Show attached tags on the card. Suggest tags already attached to documents the current user may open.
- Normalize a new tag by trimming its ends and collapsing repeated whitespace. Compare tag names without regard to letter case.
- Reject an empty tag name, control characters, commas, or a name longer than 64 characters.
- Reuse an existing tag when its normalized name matches. Preserve the spelling from that tag's first creation.
- Remove a tag from suggestions when no accessible document uses it. Keep its associations with other documents when a user removes the tag from one document.
- Show an `Add to favorites` or `Remove from favorites` star button on each card. Match its accessible name and `aria-pressed` value to the saved state, and show visible keyboard focus. Do not open the reader when the star is activated.
- Let any active signed-in user who may open a document correct its displayed title and author in the Info menu.
- Store corrected title and author values separately from source-derived metadata. Keep the source bytes and original filename unchanged.
- Use corrected title and author values on cards, in Info, and in search results.
- Show the original filename, source type, byte size, page count and its `exact`, `estimated`, or `unknown` basis, import time, and import state in Info. Show the current user's last-read date when a successful reader open has been recorded. Keep Feature 0002's indexing warning visible for `ready_with_warning` documents.
- Store tags, favorites, and corrected metadata in SQLite under the document ID. Preserve these values when Docling extraction is retried or a document is reindexed.
- Send organization and metadata changes through authenticated document-ID routes. Check document access on the server before returning or changing those values.
- If a mutation fails, show its error and restore the displayed value to the last confirmed server state.

## Reading state

- Record a reader open for the current user and document only after Feature 0003's reader successfully displays source content. Set that user's last-read time on each successful open.
- Derive `unread` when the user has no successful reader-open record and has not marked the document finished. Derive `finished` when the user's completion state is set. Derive `in progress` for every other document the user has opened.
- Show a `new` badge on a card only while its reading state is `unread`. Opening the reader removes that user's badge. Feature 0003's `Mark finished` sets `finished`; `Start over` clears completion and leaves an already opened document `in progress`.
- Do not record a reader open, change last-read time, or change reading state when the user views Feature 0004's hover preview, opens Info, searches, or downloads the source file.
- Keep reader-open records, last-read time, and completion state keyed by user ID and document ID. Do not expose one user's last-read time or reading state as another user's state.

## Search, filters, and ordering

- Extend Feature 0002's header search so a case-insensitive text query matches a substring of the displayed title, displayed author, original filename, or available Docling-extracted text. A document without extracted text remains eligible through its metadata.
- Provide filters for one source type, a case-insensitive author substring, selected tags, favorite state, and the current user's reading state. Each filter can also be left unset. For selected tags, provide `ALL` and `ANY` modes: `ALL` requires every selected tag; `ANY` requires at least one. Use `ALL` as the initial mode.
- Combine the text query and each active filter with AND. Apply the tag mode only within the selected-tag filter. Match tags by their complete normalized names. Display the active filters and provide one `Clear filters` action that resets the query and every filter.
- Apply access checks, search, and filters before pagination. Return the total count for the resulting document set, not the count of one page. Keep the configured page-size limit from Feature 0002.
- Provide newest-first and favorite-first ordering. Select newest-first by default. For newest-first, sort by import time and break ties by document ID. For favorite-first, group favorites first and use newest-first order within each group. Apply the selected ordering before pagination.
- On a fresh page load, search submission or change, or explicit sort change, apply the selected ordering to matching documents. A favorite click or live import update may change card data or add a new card, but must preserve the relative order of cards already visible. A favorite click must not immediately move the acted-on card beneath the pointer. If a changed document no longer matches an active filter, remove it after the mutation is confirmed without reordering the remaining cards.
- Show an empty-result message when no authorized document matches. When Feature 0007 introduces private documents, exclude inaccessible documents from results, result counts, tag suggestions, and extracted-text matches.

## Acceptance criteria and verification

| ID | Observable result | Verification |
| --- | --- | --- |
| AC-01 | `History` and `history` attach one reusable tag to two documents while displaying the first spelling. Removing the tag from one document leaves it on the other. Removing its final association removes it from suggestions. Invalid or overlong tag names are rejected. | Backend tag validation and association tests; browser tag and suggestion checks. |
| AC-02 | A favorite star updates its accessible name, `aria-pressed` value, and displayed state after a confirmed save. The state survives a reload and application restart. A rejected save shows an error and restores the confirmed state. Activating the star does not open the reader. | Backend persistence and rejected-mutation tests; browser pointer and keyboard checks. |
| AC-03 | A corrected title and author appear on the card, in Info, and in search results after a restart. The preserved source bytes and original filename do not change. A failed edit leaves the confirmed values visible and shows an error. | Backend metadata and source-file tests; browser Info and search checks. |
| AC-04 | Info shows the original filename, source type, byte size, import time and state, and page count with its correct basis. A `ready_with_warning` document still shows its indexing warning. The current user's last-read date appears after a successful reader open. | Browser Info checks with exact, estimated, unknown, and warning fixtures. |
| AC-05 | A user with no successful reader open sees `new` and `unread`. A successful reader open changes that user's state to `in progress` and records last-read time. `Mark finished` changes it to `finished`; `Start over` returns it to `in progress`. A second user's state remains `unread`. | Backend state tests and browser checks with two accounts. |
| AC-06 | Hover preview, Info, search, and source download leave reader-open records, last-read time, reading state, and saved reading positions unchanged. A reader that fails to open does not create a reader-open record. | Compare records before and after each action; force a reader-open failure. |
| AC-07 | Text search finds displayed title, displayed author, original filename, and available extracted text without regard to letter case. A `ready_with_warning` document without extracted text still matches its metadata. | Search tests with corrected metadata, indexed text, and extraction-failure fixtures. |
| AC-08 | Type, author, favorite, and reading-state filters combine with a text query using AND. Two selected tags match both tags in `ALL` mode and either tag in `ANY` mode. `Clear filters` restores the unfiltered set, and an unmatched search shows an empty-result message. | Backend filter tests and browser control checks with a mixed catalog. |
| AC-09 | Search and filters run before pagination. The reported total equals the number of authorized matches, each response respects the configured page-size limit, and favorite-first places favorites before other matches while preserving newest-first order within each group. | Backend pagination and ordering tests with more matches than one page. |
| AC-10 | Clicking a star or receiving a live import update does not reorder cards already visible. A later search or sort action applies the selected order. If a confirmed mutation removes a document from the active filter, the remaining cards retain their relative order. | Browser checks with delayed mutation responses, SSE updates, and multiple result pages. |
| AC-11 | Tags, favorites, and corrected metadata survive a Docling extraction retry and application restart. Anonymous requests cannot search or mutate catalog data. When document visibility is available, inaccessible documents do not appear in results, totals, or tag suggestions. | Backend retry, restart, authentication, and visibility tests. |

## Reference and boundary

Inspect the current VDL tag, favorite, search, and Info flows in `VDL/vdl.py` and `VDL/static/app.js`; use VDL feature documents 0001, 0020, and 0025 for the original user behavior. Use current VDL source where its documents differ from implementation. Keep Tomeshed changes outside `VDL/`.

Feature 0006 owns additional ingest, export, and removal workflows. Feature 0007 owns personal bookshelves and document visibility. This feature organizes existing catalog records and does not change preserved source files.
