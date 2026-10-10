# Add library file workflows

**Source:** User-requested VDL adaptation  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Feature 0002

## Decision summary

Build on the upload and catalog pipeline from Feature 0002. Add the VDL-style ways to bring local files into the library, recover or remove imports, and take originals or Docling representations out.

## User experience and behavior

- Support drag-and-drop PDF/EPUB import with an accessible file-picker equivalent. The current-import drawer shows progress, failure reason, cancellation where possible, and a path to retry without duplicate catalog records.
- Accept a direct HTTP(S) link to a PDF or EPUB as an optional import source. Fetch to a bounded temporary file, validate the actual content type, then run the same import pipeline. Show source URL in Info without treating it as a local file path.
- Offer a configured read-only watched inbox for local operators. Import a stable, eligible file into managed storage while leaving its source untouched. Record a durable receipt so an unchanged file is not imported again after restart. Define temporary-name-then-rename as the reliable producer handoff.
- Allow download/export of the preserved original and of the structured Docling JSON when conversion succeeded. Label the formats honestly; do not offer generated PDF/EPUB export unless a separate supported renderer is added.
- Allow title/author correction through Feature 0005, a safe original filename change where needed, per-document removal with confirmation, and a preview of how many records/files a bulk clear action would remove.
- Keep source files, derived documents, thumbnails, and progress records in sync when a document is removed. A failed cleanup reports remaining artifacts instead of claiming complete deletion.

## Safety and deployment

- Use the same authenticated, ID-based authorization boundary for imports, exports, and deletion. Avoid trusting browser-provided output paths or filenames.
- Limit remote URL schemes, redirects, download size, and destination networks before fetching; reject local/private targets unless an operator explicitly configures a trusted exception.
- The watched inbox must not be the managed library directory. Skip symlinks and incomplete temporary names; verify a candidate remains stable while copying.
- Provide this app's own Dockerfile and Compose configuration with separate persistent data and document storage, a health check, and a non-root runtime. Do not use or alter VDL's containers or volumes.

## Acceptance criteria

- Drag-and-drop, file picker, direct URL, and watched inbox all produce the same valid catalog record for an eligible PDF or EPUB.
- An unchanged watched file is imported once across restarts, and its source is not modified.
- Exported original bytes match the imported file; Docling JSON export is available only after successful conversion.
- Cancel, retry, single removal, and bulk clear display accurate state and leave no newly orphaned managed artifacts.
- Container restart preserves accounts, catalog, original files, and reading progress.

## Boundary

Video extraction, authenticated browser-extension downloads, transcoding, and format fallback are outside Tomeshed's document workflow.
