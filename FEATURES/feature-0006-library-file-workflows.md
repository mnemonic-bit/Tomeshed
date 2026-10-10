# Add library file workflows

**Source:** User-requested VDL adaptation  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Feature 0002

## Outcome

Let signed-in users add documents through drag-and-drop, a file picker, or a direct PDF or EPUB URL. Let an operator import files from a read-only watched inbox. Provide authorized export, stored-file renaming, and removal while preserving the import and reading contracts of Features 0002 and 0003.

## Scope and terms

- Use **import job** and the states `pending`, `processing`, `ready`, `ready_with_warning`, and `failed` as defined in Feature 0002. A `failed` job has no library card.
- Use **source file** for the preserved PDF, EPUB, or DoclingDocument JSON bytes from Feature 0002. Use **managed storage** for Tomeshed's document and generated-artifact directories.
- Use **watched inbox** for an optional, flat directory configured by the operator and mounted read-only in the container.
- Use **ingest receipt** for a SQLite record of a watched source path, its file signature, and the resulting document ID. The signature contains device, inode, byte size, and modification time at nanosecond resolution.
- Keep title and author correction in Feature 0005. Keep per-user reading positions and completion state in Feature 0003.

## Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `TOMESHED_INGEST_DIR` | Unset | Watched inbox path; unset disables the watcher. |
| `TOMESHED_INGEST_SCAN_SECONDS` | `10` | Seconds between top-level inbox scans; require a finite value of at least 1. |
| `TOMESHED_INGEST_SETTLE_SECONDS` | `60` | Minimum seconds across unchanged source signatures; require a finite value of at least 1. |
| `TOMESHED_URL_CONNECT_TIMEOUT_SECONDS` | `10` | Maximum seconds to establish a URL connection; require a positive finite value. |
| `TOMESHED_URL_TOTAL_TIMEOUT_SECONDS` | `300` | Maximum seconds for a complete URL transfer; require a positive finite value. |
| `TOMESHED_URL_ALLOWED_CIDRS` | Empty | Operator-approved destination networks in CIDR notation; an empty value adds no private-network exceptions. |

Reject an invalid configured value at startup with an error naming its setting. Apply Feature 0002's configured upload size limit to browser and URL imports.

## Browser import and retry

- Show a full-viewport drop target when a file drag enters the application. Hide it when the drag leaves or the user drops the files. Ignore text and link drags.
- Accept every file in a drop separately. Accept PDF, EPUB, and DoclingDocument JSON through both drag-and-drop and the accessible file picker. Use Feature 0002's content validation and import pipeline for each file.
- Register an import job before transferring file bytes. Show bytes received and the import job's current state in the header import drawer. After transfer, show `processing` while Feature 0002 performs extraction and thumbnail work.
- Show a filename-specific error for a failed file without cancelling successful files from the same drop. Use Feature 0002's Server-Sent Events and API reconciliation to update the drawer and catalog.
- Offer `Cancel` while a browser import is `pending` or `processing`. Persist a cancellation request and stop transfer or processing at the next safe checkpoint. Do not publish a card after cancellation is accepted.
- When cancellation finishes, set the job to `failed` with reason `Cancelled by user`. If the job already reached `ready` or `ready_with_warning`, reject cancellation and keep the document available.
- Offer `Retry` for a failed browser import. Require the user to select the local file again if its bytes are no longer stored. Create a new attempt through Feature 0002's pipeline; keep the failed attempt out of the catalog. Use Feature 0002's extraction retry for an existing `ready_with_warning` document rather than creating another document.
- On application restart, reconcile unfinished jobs through Feature 0002. Honor a persisted cancellation request before resuming processing.

## Direct URL import

- Accept a user-supplied HTTP or HTTPS URL for one PDF or EPUB source. Return a validation error without creating an import job for another scheme, URL credentials, or an empty or malformed URL.
- Register a URL import job after URL syntax validation and before the network request.
- Apply Feature 0002's upload size limit to the bytes fetched from the URL. Apply `TOMESHED_URL_CONNECT_TIMEOUT_SECONDS` and `TOMESHED_URL_TOTAL_TIMEOUT_SECONDS` to the fetch. Stop the fetch when a size or time limit is reached.
- Allow at most five redirects. Check the scheme, hostname, resolved address, and network policy for the initial URL and every redirect before connecting. Reject loopback, link-local, private, and other non-public destinations unless the operator explicitly allow-lists the destination network.
- Resolve and connect to the address that passed the network check. Do not forward Tomeshed session cookies or authorization headers to the remote server.
- Write the response to a temporary file inside managed storage. Validate the completed bytes as PDF or EPUB with Feature 0002's validator before publishing a card. Remove a rejected or incomplete temporary file.
- Show the source URL in Info after a successful import. Redact query values and omit fragments from the displayed URL. Do not treat any part of the URL as a local storage path.
- Offer `Retry` for a failed URL import by fetching the same URL in a new attempt. Keep the failed attempt out of the catalog.

## Watched inbox

- Leave the watcher disabled when no inbox is configured. If an inbox is configured, require an existing readable directory distinct from managed storage; fail startup with a named configuration error if either check fails.
- Scan the top level of the inbox at startup and every `TOMESHED_INGEST_SCAN_SECONDS`. Ignore directories, symlinks, hidden names, and temporary suffixes such as `.part`, `.tmp`, and `.download`.
- Define the producer handoff as writing an ignored temporary name, closing the file, and renaming it to a final eligible name in the same inbox. Treat a direct copy under its final name as eligible only after three identical signature observations span `TOMESHED_INGEST_SETTLE_SECONDS`.
- Check the source signature through an open file descriptor before and after copying. Check the source path signature before and after validating the managed copy. If any check differs, remove the unpublished copy and start a new settle period.
- Copy eligible PDF, EPUB, and DoclingDocument JSON files into managed storage without modifying the inbox source. Validate and process the copy through Feature 0002's pipeline.
- Track an in-flight path and signature so later scans do not start another import for the same source.
- Store the receipt and document ID in SQLite when the copied source reaches `ready` or `ready_with_warning`. Do not record a successful receipt for a `failed` job.
- If a receipt has the same path and signature, skip that source after restart and after catalog removal. If its signature changes, treat the file as a new candidate.
- After a complete successful scan finds that a source path is gone, remove that path's receipt. A later file at the same path may then enter a new settle period.
- Report a watched-file validation or copy failure in operator logs with its source path and reason. Leave the inbox source unchanged. Do not repeatedly process an unchanged failing signature during one process lifetime.
- Remove stale watcher-owned temporary copies at startup without deleting source files, completed managed files, or browser-upload partials.

## Export, rename, and removal

- Offer `Download original` for a `ready` or `ready_with_warning` document whose source file exists. Send the preserved source bytes as an attachment through an authenticated document-ID route.
- Offer `Download Docling JSON` when a valid structured artifact exists. For a DoclingDocument JSON upload, use its validated source as the structured export. For a PDF or EPUB with failed extraction, omit the structured export until extraction succeeds.
- Label the exported format and suggested filename according to the bytes sent. Do not offer a generated PDF or EPUB when only Docling JSON exists.
- Allow an active signed-in user who may open a document to rename its managed source file's basename. Reject path separators, control characters, empty names, and a target that already exists. Preserve the source extension and bytes. Update the stored path only after the rename succeeds.
- Keep the filename recorded at import as the original filename. Show the current stored filename separately after a rename, and use the current name for attachment downloads. Feature 0005 continues to search the original filename.
- Require a confirmation naming the document before single-document removal. Reject removal while that document has a `pending` or `processing` import job.
- Allow only an administrator to request a bulk-clear preview and confirm a bulk clear. Count catalog documents and existing managed source and generated files in the preview. Exclude active import jobs from bulk clear.
- If the document or managed-file set changes after the bulk-clear preview, reject the old confirmation and require a new preview. After confirmation, remove only the documents and files in the confirmed scope.
- Remove a deleted document's source file, Docling artifact, thumbnail, import and progress records, tags, favorite state, reader-open record, reading position, completion state, and shelf membership. Keep unrelated documents and inbox sources untouched.
- If cleanup fails, report the document IDs and managed artifacts that remain. Do not report the affected removal or bulk clear as complete. Persist the failed cleanup details so an administrator can retry.

## Access and deployment

- Require an active signed-in user for browser import and export. Check document access on the server before export, rename, or single-document removal. Apply Feature 0001's same-origin mutation policy.
- Resolve source and generated-artifact paths on the server from document IDs. Reject a stored path that escapes managed storage, including through a symlink. Do not accept a browser-provided filesystem path as an import, export, rename, or removal target.
- Provide Tomeshed's own root-level `Dockerfile` and `compose.yaml`. Run the application as a non-root user. Persist SQLite data and managed documents in separate volumes. Mount the configured watched inbox read-only and provide a health check.
- Preserve accounts, catalog records, ingest receipts, source files, and reading positions when the Tomeshed container is recreated against the same volumes. Do not use or modify VDL containers or volumes.

## Acceptance criteria and verification

| ID | Observable result | Verification |
| --- | --- | --- |
| AC-01 | Dragging files opens a full-viewport drop target; leaving closes it. Text and link drags do not open it. The file picker provides the same PDF, EPUB, and DoclingDocument JSON import path by keyboard and touch. | Browser drag, keyboard, and touch checks with all three formats. |
| AC-02 | Two valid files and one invalid file dropped together create separate jobs. The valid jobs show transfer progress, pass through `processing`, and produce one card each. The invalid job shows a filename-specific failure and produces no card. | Browser multi-file check and backend import-job inspection. |
| AC-03 | Cancelling a `pending` or `processing` browser import ends in `failed` with reason `Cancelled by user`, leaves no card or owned temporary file, and survives restart. A `ready` document rejects cancellation. Retrying a failed import produces one new card; retrying extraction on `ready_with_warning` retains its document ID. | Backend cancellation and restart tests; browser cancel and retry checks. |
| AC-04 | A public PDF or EPUB URL imports through the same validation pipeline as an upload. An unsupported scheme or URL credentials return a validation error without a job. An oversized response, timeout, excessive redirect, or rejected destination produces a failed job with a reason and no card or retained temporary file. | Backend URL tests with controlled HTTP responses and reduced limits. |
| AC-05 | Each URL redirect is checked against the destination policy, and the connection uses the checked address. The displayed source URL has no fragment or query values. | Backend redirect and DNS-change tests; browser Info check. |
| AC-06 | An unchanged eligible inbox file imports once across application and container restarts. Its source bytes and name remain unchanged. Deleting the catalog document does not reimport that unchanged source. | Watcher integration test with a persisted receipt and restart. |
| AC-07 | A symlink, directory, hidden name, or temporary-name file is skipped. A direct-copy file is not imported before three identical signatures span the settle period. A signature change during copying or validation removes the unpublished copy and restarts observation. | Watcher tests with reduced scan and settle settings and a changing source. |
| AC-08 | A failed watched import leaves its source unchanged and logs its path and reason. An unchanged failing signature is not retried on every scan. Removing a source prunes its receipt after a complete scan, so a later file at the path can be imported. | Watcher failure and receipt tests. |
| AC-09 | `Download original` sends bytes identical to the preserved source, including for `ready_with_warning`. `Download Docling JSON` appears only when valid structured content exists. Anonymous and unauthorized requests cannot retrieve either export. | Byte comparison and route authorization tests; browser menu checks. |
| AC-10 | Renaming a managed source changes its stored basename and download filename without changing its bytes or import filename. Unsafe names and collisions are rejected without moving the file or changing its catalog path. | Backend rename tests and browser Info and export checks. |
| AC-11 | Single removal requires confirmation and deletes only its document-owned records and managed files. A bulk-clear preview reports document and existing-file counts; only an administrator can confirm it. A stale preview is rejected. | Backend removal, role, count, and stale-preview tests; browser confirmation checks. |
| AC-12 | A forced cleanup failure reports the remaining document IDs and artifacts without claiming completion. A later retry can remove them. Unrelated documents and inbox sources remain unchanged. | Backend cleanup-failure injection and retry test. |
| AC-13 | The root Compose deployment runs Tomeshed as a non-root user with separate persistent SQLite and document volumes and a health check. When an inbox is configured, Compose mounts it read-only. Recreating the container with the same volumes preserves accounts, documents, receipts, and reading positions. | Inspect container user and mounts; restart Compose against the same volumes and read the stored records and files. |

## Reference and boundary

Inspect current VDL upload, file-serving, watcher, rename, and removal flows in `VDL/vdl.py`, its browser drop target in `VDL/static/app.js`, and its container setup in `VDL/Dockerfile` and `VDL/compose.yaml`. Use VDL feature documents 0021 and 0024 for their original user requirements; use current VDL source where a document and implementation differ. Keep all Tomeshed changes outside `VDL/`.

Video extraction, browser-extension downloads, transcoding, and video format fallback are outside this feature. Docling JSON is a structured export, not a replacement for the preserved PDF or EPUB source.
