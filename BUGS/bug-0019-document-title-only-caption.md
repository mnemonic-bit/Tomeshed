# Bug 0019 — Document captions show author and tags under the cover

**Status:** Resolved in `0.2.18`

## Observed behavior

The document caption shows title, author, and tag chips; an indexing warning can also appear beneath the cover.

## Reproduction

Open a library with a document that has an author and tags. Observe all three fields below the cover.

## Expected behavior

Show only the document name below its cover thumbnail. Put author, tags, and indexing details in the document-side panel described in Bug 0021. Preserve an accessible document name and a way to discover an indexing warning without opening an unreadable source. Long names may wrap or truncate without overlapping another card.

## Diagnosis

`static/app.js` creates `.document-copy` with title, author, tags, and optional warning. Feature 0002 requires title and author on each card, and Feature 0005 requires tags on the card; those acceptance checks need revision for this request.

## Resolution

Bug 0013 changed document cards in `0.2.18` to show only the title beneath the cover. Author, tags, and indexing details are in the reader document panel. A warning badge on the cover has an accessible label and remains visible when the source file is missing. The cover button has an accessible name based on the document title. Feature 0002 and Feature 0005 now describe the panel locations.

## Verification

**passed** — `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_documents.py` and `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_reader_panel.py` exited with code 0. A focused Chromium scenario passed at 1280 px and 390 px: a 194-character title stayed inside its card; each caption contained only one heading; the cover button retained the document name; a document with an empty author and no tags showed neither field on the card; and a missing-source document retained an accessible indexing-warning badge while its reader panel showed the author, tag, and warning text alongside the source error. This resolution changes documentation only; `VERSION` remains `0.2.18`.
