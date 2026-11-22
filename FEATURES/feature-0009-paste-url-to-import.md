# Paste a document URL to import

**Source:** User-requested URL paste workflow  
**Status:** Proposed  
**Last refined:** 2026-11-22  
**Depends on:** Features 0002, 0006, 0007

## Outcome

Let a signed-in user paste a direct document URL with Ctrl-V while Tomeshed is the active browser tab. Tomeshed adds the download to the import drawer, downloads the source file, and adds the validated document to the library through the same pipeline used by drag-and-drop. The user does not need to open the drawer, select a URL field, or confirm a second action.

## Scope and terms

- Use **import job**, **source file**, and the job states `pending`, `processing`, `ready`, `ready_with_warning`, and `failed` as defined in Feature 0002.
- Use **import drawer** for the existing `Imports` drawer. The user's list of downloads is this job list; keep URL downloads and local uploads together.
- Use **direct document URL** for an HTTP or HTTPS URL whose response contains a supported source file. A URL's extension or response content type alone does not establish that the source is valid.
- Support PDF, EPUB, and DoclingDocument JSON, matching drag-and-drop. Assumption: the requested “supported format” means all three formats. This feature extends Feature 0006's PDF/EPUB URL restriction to include DoclingDocument JSON for both pasted URLs and the existing URL form.
- Accept one URL per paste. Multiple URLs, webpage scraping, cloud-provider share-page resolution, remote login flows, and importing files or images from the clipboard are outside this feature.

## Paste interaction

1. Handle the browser's paste event in the signed-in application shell, including the library and in-app reader. Support Ctrl-V and the platform paste equivalent, including Command-V on macOS. Do not read the clipboard on tab activation or poll the clipboard.
2. If the paste target is an input, textarea, contenteditable region, or an editor that owns paste behavior, leave the paste to that control and do not start an import. Apply this rule to the search field, URL form, metadata fields, and settings fields. If a modal dialog is open, leave paste to the dialog and do not start a global import.
3. Read plain text from the paste event. Trim surrounding whitespace. If the clipboard contains files or images, do not treat accompanying text as a URL import. Do not extract links from HTML, surrounding prose, or multiple nonempty lines.
4. If the trimmed text is one HTTP or HTTPS URL, submit that URL once through the existing URL-import API. Preserve query parameters required to retrieve the source. Apply the server's URL syntax, length, and credential restrictions before creating a job.
5. If the text is ordinary prose, multiple URLs, or another scheme, leave the paste unhandled and create no job. If a submitted HTTP or HTTPS URL fails server validation, show an accessible error in the import drawer and create no job.
6. Open the import drawer when submitting a recognized URL. Show a submission indicator until registration succeeds or fails. After registration, show the job immediately, before the response body finishes downloading. Do not open the remote URL in another tab or navigate away from Tomeshed.
7. Submit at most one registration request for one paste event, including when the event bubbles through multiple handlers. Separate deliberate pastes remain separate import attempts under the existing import behavior; this feature adds no catalog deduplication rule.
8. Announce registration success or failure through an accessible status or alert. Keep the current keyboard focus when opening the drawer so a paste does not interrupt reader navigation. Keep the existing URL form available as an explicit alternative, and add brief help in the drawer describing the paste shortcut and its text-field exception.

## Download and import lifecycle

- Register a URL import job before fetching bytes. Fetch the source on the server through Feature 0006's URL-download path; do not require browser access to the remote origin.
- Show the registered job in the import drawer with a source filename or a temporary `URL download` label. Show `Downloading` while a `pending` job is transferring bytes, followed by `processing` during validation, Docling extraction, and thumbnail generation. `Downloading` is a presentation label, not a new persisted job state.
- Show received bytes during transfer. When the server supplies a valid total byte count, show received and total bytes. When the total is unknown, show received bytes without inventing a percentage. Publish transfer changes through the existing SSE and API reconciliation flow.
- Validate the downloaded bytes using the same supported-format validation as drag-and-drop. Accept a valid supported source from a URL with no extension, an unrelated extension, a query string, or a permitted redirect. Derive a safe filename with an extension matching the detected format; do not label an EPUB or DoclingDocument JSON source as PDF.
- Reject an HTML page, arbitrary JSON, empty response, corrupt source, or other unsupported content even when the URL ends in `.pdf`, `.epub`, or `.json`. A generic content type does not by itself reject a valid source.
- After download, pass the source through the existing import pipeline. Preserve the original bytes for reading and export. Use Docling for PDF/EPUB extraction and validate DoclingDocument JSON as structured input, as Feature 0002 requires.
- Publish exactly one library document for a successful job, owned by the signed-in user who registered the import, with the same initial visibility and metadata rules as a drag-and-drop import. Publish no card before validation and source storage succeed.
- Preserve `ready_with_warning` behavior when extraction fails for an otherwise valid stored PDF or EPUB. Keep the preserved source available and provide the existing extraction retry without creating another document.
- Refresh catalog results and counts after success through the existing event flow. Keep current search, filters, sorting, and reading position. If the current filters exclude the new document, announce import success without clearing those filters or claiming a matching card is visible.
- On success, remove the job from the active drawer list under the existing Imports behavior. On failure, retain the failed job and a readable reason in the drawer, remove incomplete or rejected managed files, and publish no card. Retain access to failed jobs through `Add document` after the active-job count reaches zero.
- Provide the existing `Retry` action for failed URL imports. Retry the original URL in a new attempt through the same download and validation path. Reconcile unfinished jobs after restart through Feature 0002; each job must resume from a recoverable stored source or become `failed` with a reason, without duplicate cards.

## Access and transfer constraints

- Apply the existing active-account and same-origin mutation checks to URL registration and retry. Apply the existing job-access and document-visibility checks to job responses, SSE notifications, catalog results, reading, and export.
- Preserve Feature 0006's URL protections: HTTP/HTTPS only, no embedded credentials, at most five redirects, destination checks for the original URL and each redirect, and connections to the checked address. Preserve the operator's explicit network allow-list behavior.
- Apply the configured upload size limit to streamed bytes, including responses without `Content-Length`. Preserve the configured connection and total-transfer time limits. A limit failure leaves a failed job with a reason and no source file or card.
- Do not forward Tomeshed session cookies or authorization headers to the remote host. Display source URLs with query values redacted and fragments omitted, including in drawer messages and the reader document panel. Keep retrieval query values available to the server for download and retry.

## Acceptance criteria and verification

| ID | Observable result | Verification |
| --- | --- | --- |
| AC-01 | With focus outside an editable control in the active library, one Ctrl-V of a direct PDF URL registers one job, opens the import drawer, downloads the source, and adds one library document without another action. Paste in the in-app reader and the platform paste equivalent follow the same path. | Browser checks with a controlled document server; count registration requests, jobs, and resulting documents. Exercise an actual keyboard paste in addition to dispatched paste events. |
| AC-02 | Pasting a URL into search, the URL form, a metadata field, a textarea, or a contenteditable region retains normal editing and registers no job. A modal dialog suppresses global URL import. Ordinary text, multiple URLs, HTML-only links, unsupported schemes, and clipboard files/images register no URL job. | Browser checks for each target and clipboard payload; inspect registration requests and job counts. |
| AC-03 | Leading and trailing whitespace is removed from a single URL. Retrieval query parameters reach the controlled server unchanged. Invalid credentials, malformed HTTP/HTTPS URLs, and overlong URLs produce a visible validation error and no job. One bubbling paste event produces only one registration request. | Browser paste cases and backend URL-validation tests. |
| AC-04 | A slow download appears in the drawer before completion with `Downloading` and increasing received bytes. A known total is shown; an unknown total has no fabricated percentage. The same job subsequently shows `processing`. | Browser check against throttled responses with and without `Content-Length`; inspect persisted job state and SSE/API updates. |
| AC-05 | Pasted PDF, EPUB, and DoclingDocument JSON URLs each produce one document of the detected type. Extensionless and misleading-extension URLs, generic content types, query URLs, and allowed redirects succeed for valid source bytes. The existing URL form accepts the same three formats. | Backend controlled-response matrix; browser paste and form checks for all three formats; inspect filenames and source types. |
| AC-06 | HTML disguised as PDF, arbitrary JSON, corrupt sources, empty responses, and HTTP errors produce failed jobs with reasons, no cards, and no retained rejected or partial source files. | Backend download and content-validation tests; browser failed-job check. |
| AC-07 | A pasted URL and a drag-and-drop import of the same fixture apply the same metadata, owner, initial visibility, thumbnail, and extraction rules. Exported source bytes match the downloaded fixture. Forced PDF/EPUB extraction failure gives `ready_with_warning` with an available source; extraction retry retains the document ID. | Compare import results using shared fixtures; byte comparison; extraction-failure and retry tests. |
| AC-08 | Success refreshes the catalog without changing filters, search, sorting, focus, or the open reader's position. A filter-hidden result receives a success announcement. A completed job leaves the active list; failed details remain reachable through `Add document`. | Browser checks during reading and with a filter that excludes the imported document; inspect focus, announcements, and drawer access. |
| AC-09 | A size limit, connection or total-transfer timeout, excessive redirect, or prohibited destination produces a failed job and no card or partial source. Redirect and DNS-change checks retain the existing destination protections; remote requests receive no Tomeshed credentials. | Extend URL tests with controlled responses, reduced limits, redirect destinations, DNS changes, and captured request headers. |
| AC-10 | Anonymous or suspended accounts cannot register or retry URL imports. Another user cannot read an inaccessible import job, private document, or related event metadata. Displayed URLs expose no query values or fragments. | Backend account, job-access, visibility, and event tests; browser drawer and reader-panel redaction checks. |
| AC-11 | Retry after a failed URL download starts a new attempt and yields one document when the response becomes valid. Restart during transfer or processing reconciles the unfinished job to resumed processing or a failed job with a reason, without duplicate cards. SSE reconnection refreshes job and catalog state. | Backend retry and restart tests; browser disconnect/reconnect check. |
| AC-12 | The drawer documents the paste shortcut. Registration and validation feedback is announced accessibly. Drag-and-drop, local file selection, and the explicit URL form remain usable. | Browser keyboard, status/alert, and import-path regression checks. |

## Current baseline and implementation references

Baseline inspected: Tomeshed `VERSION` `0.4.18`. `static/app.js` contains the explicit URL-form submission, `importFiles`, and `loadImportJobs`. `templates/index.html` contains the Imports drawer and the PDF/EPUB URL label. `file_workflows.py` registers URL jobs at `POST /api/imports/url`; `FileWorkflows.fetch_url` restricts downloaded content to PDF/EPUB and delegates processing to the document library. Update those format restrictions and labels when implementing DoclingDocument JSON parity.

Use `tests/test_file_workflows.py` and `tests/browser_check_file_workflows.py` as existing verification references. Record implementation results in `FEATURES/evidence/feature-0009.md` when the feature is built; this specification records no implementation acceptance results.

Inspect `VDL/static/app.js`, `VDL/templates/index.html`, and `VDL/vdl.py` for comparable clipboard, job-list, and background-download flows before implementation. Reference limitation: `VDL/` is absent from the checkout used to write this specification, so its current behavior was not verified. Keep all Tomeshed changes outside `VDL/` and preserve the document-specific import contract.
