# Import and browse a searchable document library

**Source:** User-requested first version  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Feature 0001

## Outcome

Give a signed-in user a responsive library of PDF, EPUB, and DoclingDocument JSON files. The user can upload a file, find a document by title, author, or original filename, and open the preserved source from a document card. Use Docling to extract structured content for indexing and later processing.

## Scope and terms

- Accept browser uploads in this feature. Feature 0006 adds other import paths.
- Use **source file** for the uploaded PDF, EPUB, or DoclingDocument JSON bytes. Preserve the source file for reading and download.
- Use **document** for a catalog record with a stable, opaque document ID. Store catalog records and import jobs in SQLite. Store source files and generated artifacts in managed library storage.
- Use **import job** for the work that validates, stores, and processes one upload. Record its state as `pending`, `processing`, `ready`, `ready_with_warning`, or `failed`. `ready` and `ready_with_warning` documents appear in the library. A `failed` job does not create a library card.
- Use **indexing warning** when a valid PDF or EPUB source is available but Docling extraction fails. A document with this warning has state `ready_with_warning`; its extracted text is unavailable until a retry succeeds.
- Keep document reading in Feature 0003, hover preview in Feature 0004, metadata editing and richer search in Feature 0005, and additional import paths in Feature 0006.

## Import and processing

- Accept PDF, EPUB, and DoclingDocument JSON uploads. Reject a file whose content is not a valid instance of one of those formats, regardless of its filename extension.
- Assign each accepted source a stable, opaque document ID. Store the source bytes in managed library storage before publishing a document card.
- Convert PDF and EPUB sources with Docling's `DocumentConverter` and an explicit PDF, EPUB, and Docling JSON input allow-list. Validate a DoclingDocument JSON upload as a structured document; treat that upload as the structured source.
- Persist the DoclingDocument JSON representation, or a derived artifact that can be reproduced from the source, for indexing and later processing. Do not replace a PDF or EPUB source with Docling output.
- Extract title, author, source type, byte size, and searchable text when available. If the source has no title, use a cleaned original filename. If the source has no author, show `Unknown author`. Do not create bibliographic values that the source does not provide.
- If validation or source storage fails, set the import job to `failed` and show the failure reason. Do not publish a library card for that job.
- After successful validation, source storage, and extraction, set the import job to `ready` and publish the document card.
- If Docling extraction fails for a valid, stored PDF or EPUB, set the document to `ready_with_warning`. Keep the source available, show an indexing warning, and provide a retry action. Do not claim that unavailable extracted text is searchable.
- On an extraction retry, keep the source and card available. If the retry succeeds, set the document to `ready` and clear the indexing warning. If the retry fails, keep `ready_with_warning` and show the new error.
- Generate or extract a cover or first-page thumbnail. Associate the generated artifact with the document ID.
- If thumbnail generation fails, keep the valid document in the library and show artwork for its source type.
- Reconcile `pending` and `processing` jobs after an application restart. Resume work when its stored source is available; otherwise mark the job `failed` with a reason.
- Show `pending`, `processing`, and `failed` jobs in a header import drawer. Send import-state changes through Server-Sent Events (SSE). After the SSE connection returns, refresh job and catalog state through the normal API.
- Run conversion and image processing in a background job after the upload request returns. Reject uploads above the configured size limit with a clear error. Enforce configured conversion time and concurrency limits; record a time-limit failure in the affected import job without changing existing documents.

## Library view

- Use the centered, responsive thumbnail-card layout and visual language of the current VDL library. Keep portrait covers legible against a neutral preview background.
- Show the document title beneath each thumbnail. Make each thumbnail selectable with one click and open the reader with a double-click or Enter. Put author and other document details in the reader's left panel. Keep the thumbnail action usable when generated artwork is missing.
- Open an authenticated document detail from a card. Give the detail view access to the preserved source. Feature 0003 changes card activation to the in-app reader.
- Show source type, page count, and count basis in the reader document panel. Show a PDF's actual page count as exact.
- For an EPUB with extracted text, calculate an estimated page count once as `ceil(word_count / 300)`, with a minimum of one for nonempty text. Store the estimate and show its estimated basis in the reader document panel. If extraction yields no words, show an unknown count.
- For DoclingDocument JSON, show an exact page count only when the source contains stable page data. Otherwise show an unknown count. Do not store viewport-dependent pagination as an exact count.
- Provide a header search field that matches title, author, and original filename without regard to letter case. Show an empty-result message when no document matches. Keep search and card actions keyboard accessible. Feature 0005 adds tags and document-text search.
- Show the total number of library documents in the fixed footer. Limit each catalog response to the configured maximum page size and load additional pages on demand.
- Show source type, title, author, byte size, import state, and any import or indexing error in the reader document panel. Feature 0005 adds editing and organization actions.

## API and access boundary

- Return the stable document ID, title, author, source type, page count, count kind (`exact`, `estimated`, or `unknown`), thumbnail availability, and import state from the catalog API. Later reader, preview, and organization features use this record.
- Serve source files and generated thumbnails through authenticated routes that address a document ID. Resolve stored paths on the server, verify that each resolved path stays inside managed storage, and check access before sending bytes.
- Reject anonymous requests to list or search documents and to retrieve source files or thumbnails.

## Acceptance criteria and verification

| ID | Observable result | Verification |
| --- | --- | --- |
| AC-01 | A signed-in user uploads a valid PDF, EPUB, and DoclingDocument JSON file. Each source has a stable document ID and appears as one card after import. The PDF and EPUB fixture cards show generated thumbnails. Each card opens an authenticated detail that gives access to the preserved source. | Backend import and source-route tests; browser upload and card checks. |
| AC-02 | A corrupt or unsupported upload produces a `failed` job with a reason and no library card. The import drawer shows `pending`, `processing`, and `failed` jobs as applicable. | Backend validation and job-state tests; browser import-drawer check. |
| AC-03 | A valid PDF or EPUB remains openable when Docling extraction fails. Its card has an accessible indexing warning indicator, and the reader document panel shows `ready_with_warning` and the error. Unavailable extracted text is not reported as searchable. A successful retry clears the warning, and a failed retry keeps the source available. | Force extraction failure and both retry outcomes in import tests; inspect the catalog response, source route, and browser warning. |
| AC-04 | Missing source title appears as the cleaned filename on the card; missing author appears as `Unknown author` in the reader document panel. A failed thumbnail displays source-type artwork without disabling the card. | Import fixtures with missing metadata and a forced thumbnail failure; inspect the card and reader document panel. |
| AC-05 | A 12-page PDF has count kind `exact` and shows 12 pages in the reader document panel. An EPUB with 601 extracted words has count kind `estimated` and shows 3 estimated pages there. An EPUB with no extracted words and Docling JSON without stable page data show an unknown count. | Import fixtures with known page data and word counts; inspect catalog responses and the reader document panel. |
| AC-06 | Header search matches title, author, and original filename regardless of letter case. A query with no matches shows an empty-result message. Search and card actions work with a keyboard. | Browser search and keyboard checks against a catalog fixture. |
| AC-07 | The footer shows the total catalog count. The first catalog response contains no more than the configured maximum page size, and additional documents load on demand. Cards remain usable at 390 px and 1280 px viewport widths. | Backend pagination test with more documents than the configured page size; browser count and viewport checks. |
| AC-08 | Anonymous requests cannot list, search, or retrieve documents or thumbnails. A manipulated document ID cannot read a file outside managed storage. | Backend authentication, authorization, and path-manipulation tests. |
| AC-09 | After an application restart during processing, each affected job resumes from its stored source or becomes `failed` with a reason. Existing source files remain associated with their document IDs. | Restart the app with `pending` and `processing` job fixtures; inspect job states, document IDs, and source routes. |
| AC-10 | Import-state changes reach an open browser through SSE. After the SSE connection returns, the browser refreshes jobs and cards from the API. | Browser check with a controlled SSE disconnect and reconnect. |
| AC-11 | An upload above the configured size limit returns a clear error. A conversion that exceeds the configured time limit produces a `failed` job with a reason and leaves existing catalog records and source files intact. | Backend tests with reduced upload and conversion time limits. |
| AC-12 | The library cards use VDL's centered layout and portrait preview treatment. Each document card shows its title beneath the thumbnail; document details appear in the Tomeshed reader's left panel. | Compare Tomeshed and current VDL card screenshots at 390 px and 1280 px widths; inspect the reader panel separately. |

## Reference and boundary

Inspect the current VDL implementation when implementing a comparable flow: `VDL/vdl.py` for SQLite, file access, and SSE; `VDL/templates/index.html`, `VDL/static/app.js`, and `VDL/static/styles.css` for cards and the import drawer; and `VDL/tests/` for verification patterns. Use the current source when a VDL feature document differs from the implementation. Keep all Tomeshed changes outside `VDL/`.

Docling supports PDF, EPUB, and Docling JSON input and exports structured JSON; its output is not a PDF or EPUB replacement. EPUB pagination can vary with layout, so the library labels a derived count as estimated. Sources: [Docling supported formats](https://docling-project.github.io/docling/usage/supported_formats/), [DocumentConverter API](https://docling-project.github.io/docling/reference/document_converter/), [W3C EPUB pagination guidance](https://www.w3.org/TR/epub-a11y-explain-12/).
