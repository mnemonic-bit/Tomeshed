# Bug 0019 — Document captions show author and tags under the cover

**Status:** Open

## Observed behavior

The document caption shows title, author, and tag chips; an indexing warning can also appear beneath the cover.

## Reproduction

Open a library with a document that has an author and tags. Observe all three fields below the cover.

## Expected behavior

Show only the document name below its cover thumbnail. Put author, tags, and indexing details in the document-side panel described in Bug 0021. Preserve an accessible document name and a way to discover an indexing warning without opening an unreadable source. Long names may wrap or truncate without overlapping another card.

## Diagnosis

`static/app.js` creates `.document-copy` with title, author, tags, and optional warning. Feature 0002 requires title and author on each card, and Feature 0005 requires tags on the card; those acceptance checks need revision for this request.

## Proposed resolution

Keep the title line as the sole visible text below the thumbnail. Move the other fields to the reader's document-side panel and keep their state available to assistive technology where it affects whether the document can open.

## Verification

**not_run** — Documentation only. Check cards with long titles, missing authors, tags, and indexing warnings at desktop and mobile widths; confirm the panel contains the moved information.
