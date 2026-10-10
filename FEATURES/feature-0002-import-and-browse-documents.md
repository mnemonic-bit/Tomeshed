# Import and browse a searchable document library

**Source:** User-requested first version  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Feature 0001

## Decision summary

Make the default Tomeshed view a responsive library of PDF, EPUB, and DoclingDocument JSON documents. A signed-in user can add a file, search the catalog, and see a clickable thumbnail card for each completed import. Use Docling as the backend extraction and normalized-document layer while retaining the source file.

## Import and catalog

- Accept local PDF, EPUB, and valid DoclingDocument JSON files in this slice. Store the original bytes in a managed library directory and give each document an opaque, stable ID. Feature 0006 adds other ingest paths.
- Validate the actual file format and reject unsupported or corrupt files with a useful error. Publish a catalog entry only after the source is safely stored and identified. A valid PDF or EPUB remains readable if Docling extraction fails; show an indexing warning and retry option instead of claiming searchable content exists. Invalid Docling JSON cannot become a readable entry.
- Convert with Docling's `DocumentConverter` using an explicit PDF/EPUB/Docling JSON allow-list. Persist a DoclingDocument JSON representation or a reproducible derived artifact for search and later processing. Keep PDF and EPUB originals as the source for reading and download; Docling is not a PDF/EPUB round-trip renderer. A Docling JSON upload is already the structured source.
- Extract title, author, type, size, and searchable text when available. Fall back to a cleaned filename for a missing title and show a clear unknown author state. Do not invent bibliographic metadata.
- Persist the catalog and import state in SQLite. Reconcile interrupted imports on restart. Show active and failed imports in a header drawer, with live state updates through SSE and a normal API refresh path after reconnecting.
- Generate or extract a cover/first-page thumbnail. A failed thumbnail falls back to type-specific artwork without losing a valid import. Keep generated artifacts associated with the stable document ID.

## Library view

- Use VDL's centered, responsive thumbnail-card layout and visual language. Keep book covers legible within the card's preview area; use a neutral background for portrait artwork.
- Each card shows the title, author when known, a three-dot Info/action menu, and an actionable thumbnail. In this slice, activation opens an authenticated document detail with access to the preserved original. Feature 0003 changes activation to the in-app reader. A card stays usable when its thumbnail is missing.
- Put a compact `TYPE · N pages` badge in the lower-right corner of the thumbnail, in the position of VDL's resolution badge. PDF uses the document's actual page count. EPUB uses `~N pages` for a stable estimate and labels it as estimated; if no defensible count exists, show `EPUB · pages unknown`. Docling JSON uses an exact count only when it contains stable page data, otherwise `DOCLING · pages unknown`. Do not present viewport-dependent pagination as an exact stored fact.
- Derive the EPUB estimate once from successfully extracted text as `ceil(word_count / 300)`, with a minimum of one for nonempty text. Mark it unknown when extraction yields no words. Store the result so a new screen size does not silently change the library badge.
- Provide a header search field that filters by title, author, and original filename, case-insensitively. Include an empty-result state and preserve keyboard access. Feature 0005 extends search to tags and document text.
- Show total catalog count in the fixed footer. Use server-side pagination or bounded loading so a large catalog does not make the initial page unresponsive.
- The Info menu shows source type, title, author, size, import status, and import error when applicable. Later editing and organization actions belong to Feature 0005.

## API boundary

- Give the catalog API a stable document ID and fields for title, author, type, page count, count kind (`exact`, `estimated`, or `unknown`), thumbnail availability, and import state. The reader, preview, and organization features consume this record rather than parsing card markup.
- Serve originals and generated thumbnails only through authenticated, document-ID-based routes. Resolve stored paths server-side, verify they remain inside managed storage, and check authorization before sending bytes.
- Keep upload, conversion, and image processing off the request path when work can exceed a normal HTTP request. Limit upload size and processing resources, and surface failure without corrupting existing catalog entries.

## Acceptance criteria

- A signed-in user imports a PDF, EPUB, and valid DoclingDocument JSON file, sees one card for each, searches by title/author/filename, and can access each original from its card.
- A 12-page PDF shows `PDF · 12 pages`; an EPUB badge marks any derived count with `~` and accessible estimated wording.
- Missing covers and missing metadata use visible fallbacks; a corrupt file produces a failed import state and no ready document. A valid source remains openable with a visible indexing warning when Docling extraction fails.
- Anonymous requests cannot list, search, or retrieve source files or thumbnails. Path-manipulated IDs cannot escape managed storage.
- Restarting during conversion leaves a recoverable or clearly failed job, and the original library files remain associated with the correct records.

Sources: [Docling supported formats](https://docling-project.github.io/docling/usage/supported_formats/), [DocumentConverter API](https://docling-project.github.io/docling/reference/document_converter/), [W3C EPUB pagination guidance](https://www.w3.org/TR/epub-a11y-explain-12/).
