# Add personal bookshelves

**Source:** User-requested VDL adaptation  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Features 0002 and 0003

## Outcome

Let a signed-in user organize documents into ordered personal bookshelves and resume a document from a bookshelf at that user's saved reading position. Let the bookshelf owner share a read-only bookshelf with named users. Keep bookshelf access separate from document visibility so a share never grants access to a private document.

## Scope and terms

- Use **bookshelf** for a named collection owned by one user. A document may occur once in a bookshelf and may belong to several bookshelves.
- Use **membership order** for the saved order of documents within one bookshelf. Use **bookshelf order** for the saved order of one owner's bookshelves in the library.
- Use **bookshelf bookmark** for the last document that one user successfully opened from one bookshelf. Keep its document ID in SQLite under the user ID and bookshelf ID. Keep the actual reading position under the user ID and document ID as defined in Feature 0003.
- Use `public` and `private` for document visibility. A `public` document is available to active signed-in users. A `private` document is available to its owner and administrators.
- Use **system-owned document** for a document imported without an interactive user, such as a watched-inbox import, or migrated from a catalog without ownership data. Administrators manage its visibility.
- Apply this feature to `ready` and `ready_with_warning` documents from Feature 0002. Use Feature 0005's reading state and Feature 0006's document-removal lifecycle when those features are present.

## Document ownership and visibility

- Assign a browser or direct-URL import to the active user who started the import. Assign a watched-inbox import to system ownership. Assign existing documents without an owner to system ownership during migration.
- Set every new and migrated document to `public` unless an existing visibility value is already stored.
- Let a document owner or administrator change that document between `public` and `private`. Reject a visibility change by another user with HTTP 403.
- Keep a system-owned `private` document available only to administrators.
- If an account is removed, keep its documents and their visibility values. Transfer those documents to system ownership so administrators can manage them.
- Check document visibility on the server before returning a card, search result, result count, tag suggestion, Info data, thumbnail, reader or preview content, source file, or export. Return HTTP 404 for both an unknown document ID and a private document the requester cannot access.
- Check document visibility again when a user activates a bookshelf document. Do not rely on a document ID or bookshelf membership supplied by the browser as authorization.
- Omit private-document identifiers and metadata from change events sent to users who cannot access the document.

## Bookshelf creation and editing

- Let an active signed-in user create, rename, reorder, and delete their own bookshelves. Keep bookshelves private until the owner adds named recipients.
- Require a bookshelf name with 1 to 120 visible characters after trimming surrounding whitespace. Reject control characters with HTTP 400. Permit different bookshelves to have the same name.
- Show `My bookshelves` and `Shared with me` as distinct sections above the document grid. Do not count bookshelf cards as catalog documents or consume catalog page slots.
- Show each bookshelf's name and the count of documents visible to the current viewer. Show cover previews only for documents the viewer may open. Show an empty state when no documents are visible.
- Open a bookshelf detail with its accessible documents in membership order. Show each document's cover, displayed title, and source type. If Feature 0005 is implemented, show the current viewer's reading state; otherwise omit the reading-state label.
- Provide `Add to bookshelf` on an accessible document card. Offer only bookshelves owned by the current user in that action.
- Let the owner add, remove, and reorder documents in a bookshelf editor. Require each added document to be visible to the owner and in state `ready` or `ready_with_warning`. Reject duplicate document IDs within one bookshelf.
- If the owner later loses access to a member, show an `Unavailable document` placeholder in the editor with a remove action. Do not show its title, filename, or cover.
- Provide keyboard-accessible move controls for both bookshelf order and membership order. Save each order as gapless positions beginning at zero.
- Save bookshelf order with an expected owner-order revision. If another session has saved a newer order revision, return HTTP 409 and leave the saved order unchanged.
- Save a bookshelf name and complete ordered membership atomically with a bookshelf revision number. If another session has saved a newer bookshelf revision, return HTTP 409 and the current bookshelf for review. Leave the saved name and membership unchanged after a rejected edit.
- Require confirmation before deleting a bookshelf. Remove only the bookshelf, its shares, memberships, and bookshelf bookmarks. Keep its documents, source files, tags, and per-document reading positions.
- If Feature 0006 removes a document, remove its membership from every bookshelf and compact the remaining positions. Clear a bookshelf bookmark that points to the removed document.

## Sharing and read-only access

- Let the owner share a bookshelf by entering an exact username. Resolve that username to an active account ID on the server. Reject an unknown or suspended username and the owner's own username.
- Let the owner revoke an individual share. After revocation, reject that recipient's bookshelf requests, including requests from an already open browser session.
- Let a recipient list and open a shared bookshelf. Reject rename, membership changes, reordering, deletion, and share changes by a recipient with HTTP 403. Do not grant administrators access to another user's bookshelf unless the owner shares it with them.
- Let a recipient update only their own bookshelf bookmark by opening a document from the shared bookshelf. Do not change the owner's bookmark or membership order.
- Filter a shared bookshelf's members through the recipient's current document access on every response. Return only accessible document IDs, metadata, cover URLs, and a count of accessible members. Give visible members consecutive display positions.
- If a document becomes `private` after a bookshelf was shared, retain its membership record but remove it from every viewer's detail when that viewer lacks document access. Do not reveal the hidden document through member counts, cover previews, search, or a bookshelf bookmark.
- If a shared bookshelf contains no accessible documents, show its name and an empty state. Disable `Continue reading` for that recipient.

## Continue reading

- When a user successfully opens a document from a bookshelf, save that document as the user's bookshelf bookmark for that bookshelf. Do not update a bookshelf bookmark when the reader fails to open.
- Keep bookshelf bookmarks separate for the owner and each recipient. Opening the same document outside a bookshelf does not change any bookshelf bookmark.
- On `Continue reading`, open the current user's bookmarked document if it remains in the bookshelf, the user may access it, and its source file is present. Otherwise open the first accessible document with a present source file in membership order. Disable the action when no such document exists.
- Restore the chosen document at the current user's saved reading position through Feature 0003. If the user has no saved position, start at the beginning. Do not copy another user's reading position or change positions in other documents.
- If a bookmarked document is removed, becomes inaccessible, or loses its source file, clear the unusable bookmark before selecting the first accessible member with a present source file. Preserve the user's per-document reading position in case access or the source later returns.
- If a user opens a different document from the bookshelf, update only that user's bookmark for that bookshelf. Keep bookmarks in other bookshelves unchanged.

## Persistence and access

- Store bookshelf owner, bookshelf order, owner-order revision, membership order, bookshelf revision, shares, and per-user bookshelf bookmarks in SQLite. Preserve these records across application restarts and concurrent browser sessions.
- Enforce bookshelf ownership or an explicit share on every bookshelf read. Enforce ownership on every bookshelf mutation. Return HTTP 404 for both an unknown bookshelf ID and a bookshelf the requester cannot read.
- Apply Feature 0001's same-origin mutation policy to visibility, bookshelf, and sharing changes. Do not return another user's bookshelf bookmark or reading position in a bookshelf response.
- If a user account is removed, delete that user's owned bookshelves and shares addressed to that user. Keep catalog documents and other users' per-document reading positions.

## Acceptance criteria and verification

| ID | Observable result | Verification |
| --- | --- | --- |
| AC-01 | A user creates two bookshelves with the same name, reorders them, and sees their saved order after reload and application restart. An empty bookshelf remains visible with `Continue reading` disabled. Invalid names are rejected. | Backend creation, validation, ordering, and restart tests; browser empty-state check. |
| AC-02 | A document can appear in two bookshelves but only once in each. The owner can quick-add from a card, move members by keyboard, and remove a member without deleting its document or saved reading position. | Backend membership tests and browser quick-add and keyboard checks. |
| AC-03 | An editor save changes name and membership order together. A stale bookshelf revision returns HTTP 409 with the current bookshelf and leaves the saved name and membership unchanged. A stale owner-order revision returns HTTP 409 without changing bookshelf order. | Backend concurrent-edit tests with two sessions; browser conflict check. |
| AC-04 | The bookshelf section shows names, accessible member counts, and accessible cover previews without changing the document-grid count or pagination. Its detail lists accessible documents in order with cover, displayed title, and source type; when Feature 0005 is present, it also shows the viewer's reading state. A recipient sees `Shared with me` separately from owned bookshelves. | Browser checks with more catalog documents than one page and a shared bookshelf; include the reading-state label check when Feature 0005 is present. |
| AC-05 | Opening a bookshelf document records a bookshelf bookmark for that user and bookshelf. `Continue reading` restores the same document at that user's PDF page, EPUB location, or Docling element after sign-out, browser reload, and application restart. Another user's document position and bookshelf bookmark remain independent. | Browser resume checks with two accounts and PDF, EPUB, and DoclingDocument JSON fixtures; inspect SQLite records. |
| AC-06 | Opening a document outside a bookshelf leaves the bookshelf bookmark unchanged. Removing, hiding, or losing the source file for the bookmarked document makes `Continue reading` choose the first accessible member with a present source file. The action is disabled when no such member exists. | Backend bookmark, visibility, and missing-file tests; browser resume-target checks. |
| AC-07 | A recipient can read a shared bookshelf but cannot rename, reorder, add, remove, delete, or reshare it. An unshared user, including an administrator, cannot read the bookshelf. Unknown and suspended usernames cannot be added as recipients. Revocation ends recipient access in an already open session. | Backend authorization and revocation tests with owner, recipient, administrator, and unshared user. |
| AC-08 | A shared bookshelf containing a private document returns only the recipient's accessible members, covers, count, and consecutive display positions. Making a visible member private hides it from viewers without access while preserving its membership. An owner who loses access sees only an `Unavailable document` editor placeholder for that member. | Backend visibility-change tests and browser checks with a mixed-access bookshelf. |
| AC-09 | A private document is absent from unauthorized catalog responses, search totals, tag suggestions, thumbnails, reader and preview routes, source and export routes, and change events. Unknown and inaccessible document IDs both return HTTP 404. | Backend route and event tests with two users; direct requests to each document route. |
| AC-10 | Browser and URL imports belong to their importing user; watched and migrated documents are system-owned. A document owner or administrator may change visibility, while another user cannot. Removing an owner account leaves its documents manageable by an administrator with their visibility unchanged. | Backend import, migration, visibility, and account-removal tests. |
| AC-11 | Deleting a bookshelf leaves its member documents and reading positions intact. Removing a document through Feature 0006 removes it from every bookshelf, compacts member order, and clears bookshelf bookmarks to that document. | Backend deletion and referential-integrity tests; browser bookshelf check after removal. |

## Reference and boundary

Inspect VDL's current playlist and document-visibility logic in `VDL/vdl.py` and its playlist browser controls in `VDL/static/app.js`. Use `VDL/FEATURES/feature-0031-add-personal-video-playlists.md` for the original collection requirements, and use current source where it differs from that document. VDL playlists are owner-only; Tomeshed adds explicit read-only bookshelf sharing while keeping document access independent.

Bookshelves do not advance automatically from one document to another and do not add shuffle or video playback controls. Keep all Tomeshed changes outside `VDL/`.
