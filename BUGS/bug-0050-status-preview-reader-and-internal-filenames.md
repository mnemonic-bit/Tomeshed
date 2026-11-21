# Bug 0050 — Redundant connection status, hidden preview controls, and exposed storage filenames

**Status:** Resolved locally in `1.0.0`.
**Reported baseline:** `0.4.19`
**Scope:** Correct the status bar, preview navigation visibility, reader downloads, and source filename handling.

## Observed behavior

- The bottom status bar shows `Connected` during normal operation. The user reports that existing connection-failure and version-mismatch messages already provide the necessary exception information.
- Preview Previous and Next buttons are completely transparent until their activation region is hovered or a supported focus or touch interaction reveals them. The user reports that the buttons are difficult to discover.
- The full-content reader puts `Download original`, including its available-format menu, in the document sidebar rather than the top bar.
- The reader sidebar exposes an editable `Stored filename`. Saving that field renames the source file on the server.
- The main file workflow stores sources as `sources/<document UUID>/<original filename>`. Original export uses the server basename as the download filename. A separate upload path already stores sources as `sources/<document UUID>.source` and uses the original filename for source downloads.

The current UUID-based directories already separate files with identical names. No filename collision or data loss has been reproduced. The storage defect is the remaining dependence on user filenames for server basenames and the exposure of server naming through the reader and downloads.

## Reproduction

1. Open the library while the server is reachable and versions match. Observe `Connected` in the bottom status bar.
2. Hover over a document thumbnail to open its preview. Keep the pointer away from the navigation activation regions. Observe that the navigation buttons are invisible, then move over each region to reveal its button.
3. Open a document in the full-content reader. Observe `Download original` in the sidebar and the paging and scaling controls in the top bar.
4. Find `Stored filename` in the sidebar. Activate its editor and save a different name. The rename endpoint changes the server source path.
5. Import two distinct supported files with the same local basename. Inspect their server source paths. The main import workflow separates the files by document UUID directory but retains the local basename on disk.
6. Download an original through `/api/documents/<document_id>/export/original`. The current handler takes the suggested download name from the server basename, coupling the user-facing filename to storage naming.

The initial report recorded these reproduction steps without a browser run. Implementation verification reproduced the healthy status label and invisible resting preview buttons in Chromium, and the backend regression reproduced the user filename used as a server basename.

## Expected behavior and acceptance criteria

### AC-1 — Remove the routine connection label

Remove `Connected` from the bottom status bar during healthy operation. Remove any separator or empty space left by that label. Preserve health checks, connection-failure messages, version-mismatch messages, and the remaining footer information. Verify healthy, unreachable-server, version-mismatch, and recovered-connection states in the browser.

### AC-2 — Make preview navigation faintly visible at rest

Show a faint, highly translucent outline of both preview navigation buttons before hover. Hovering each button or its existing activation region restores that button's current revealed appearance. Moving away restores the faint appearance. Preserve keyboard focus visibility, touch access, accessible names, and disabled behavior at the first and last locations. Verify a nonzero resting opacity below the revealed opacity, then visually check discoverability over light and dark content in both themes. Preserve the current button placement and preview dimensions.

### AC-3 — Move downloads into the reader top bar

Place `Download original` in the full-content reader's top bar, immediately to the left of the paging and scaling controls group. Move the existing available-format menu with the download control so converted exports remain accessible. Remove the duplicate sidebar control. Keep downloads available when the sidebar is minimized. Verify PDF and EPUB downloads, keyboard access, and a narrow viewport without overlapping controls.

### AC-4 — Keep storage naming internal

Remove the editable `Stored filename` control and its rename action from the reader. Do not display the server basename, UUID storage filename, or storage path as document filename metadata. Continue to show the original user filename as read-only metadata. Title and Author remain editable. Verify that the reader provides no stored-filename edit path and that a direct request to the former rename endpoint cannot change the internal storage name.

### AC-5 — Use UUID-based source filenames

Use an internally generated UUID as each server source basename rather than the original user filename; a required format suffix may be retained. Preserve the original user filename separately as metadata. Apply this separation to browser uploads, URL imports, watched-folder imports, and retries. Keep existing documents readable through a migration or compatibility path, and document how existing filename-based sources are handled. Preserve source bytes and keep source-path references consistent across document and import records.

Verify two different files with the same user filename, including concurrent imports. Each source must have a distinct internal UUID storage name, retain its own bytes and original filename, and remain readable and downloadable. Verify that title or author changes do not rename source files. Verify existing documents, retry, preview, reading, and removal after the storage change. Do not claim an existing collision as the motivation without evidence.

### AC-6 — Preserve user filenames on download

Use the original user filename, subject to existing basename and header safety validation, for original downloads regardless of the UUID storage name. Apply the rule to the reader download action, original-export endpoint, source-download endpoint, and bulk original exports. Never substitute the internal UUID storage basename in a suggested filename or archive entry. If multiple originals share a name in one archive, disambiguate entries with a readable suffix while preserving their extensions. Verify filenames and unchanged source bytes for PDF and EPUB originals, including spaces, Unicode, and duplicate names. Preserve export authorization and available converted formats.

## Diagnosis

Initial source inspection identified the following implementation points in the reported baseline:

- `static/app.js`, `checkHealth()`, writes `Connected` to `#connectionStatus`; `templates/index.html` renders that element and footer separators.
- `static/styles.css`, `.document-preview-bubble .preview-nav-hit button`, sets resting opacity to `0`; hover, keyboard focus, and touch rules set opacity to `1`.
- `static/app.js`, `renderDocumentInfo()`, appends `panelDownloads()` to sidebar details and creates the `stored_filename` inline editor using `POST rename-file`.
- `file_workflows.py`, `FileWorkflows.register()`, uses `sources/<document_id>/<name>` for source storage. The original-export handler uses `source.name` for the download name. Bulk export also derives archive entry names from the source basename in the usual case.
- `file_workflows.py`, `rename_file()`, changes both the source basename and the document's `source_path`. `organization_service.py` exposes that basename as `stored_filename`.
- `document_library.py` has a UUID `.source` upload path and a source-download handler that already falls back to `original_filename` for that storage form. These behaviors need to remain consistent with the main file workflow.

The regression checks confirmed three independent causes: healthy health checks wrote a routine label; preview CSS forced resting opacity to zero; and imports, exports, metadata, and renaming coupled server basenames to user filenames. The old rename endpoint also updated the document path without updating historical import-job paths. The read-only `VDL/` blueprint is absent from this checkout, so no VDL comparison was possible.

## Related reports and requirement precedence

- [Bug 0047](bug-0047-footer-document-count-and-uptime.md) covers footer counts and uptime. AC-1 supersedes its instruction to keep routine connection information; the version information and count/uptime requirements remain.
- [Bug 0038](bug-0038-document-preview-controls-and-spacing.md) introduced fully hidden resting navigation buttons. AC-2 replaces that resting visibility requirement.
- [Bug 0031](bug-0031-reader-document-panel-redesign.md) introduced sidebar downloads and stored-filename editing. AC-3 through AC-6 supersede those placement and filename-editing requirements.
- [Bug 0032](bug-0032-reader-header-controls-and-zoom.md) defines the reader top-bar paging and scaling group that the download control must precede.

## Resolution

- Healthy health checks hide and clear `#connectionStatus` and hide its separator. Connection errors and version mismatches remain visible, and recovery clears the exception state.
- Preview navigation uses resting opacity `0.18`. Existing activation regions, hover, keyboard focus, touch access, placement, and dimensions remain in place.
- The reader top bar renders the original-download control and available-format menu immediately before navigation and zoom. Downloads remain available with the document panel minimized. Narrow layouts wrap controls without overlap.
- The reader shows the original user filename as read-only metadata. Title and Author remain editable. The document API no longer exposes `stored_filename`; the former rename endpoint checks access and returns HTTP 409 without changing files or database paths.
- New registered imports use `sources/<document UUID>/<document UUID>.source`. The multipart upload path continues to use `sources/<document UUID>.source`. URL format detection updates original filename metadata without renaming the UUID source. Browser, URL, watched-folder, and retry flows preserve source bytes and source-path references.
- Original exports, source downloads, and bulk original exports use safe original filename metadata. Duplicate archive entries receive readable numeric suffixes before the extension. Archive naming reserves `manifest.json` for the export manifest.
- Existing sources keep their recorded paths; no source-file migration runs. Startup synchronizes historical import-job source paths with the corresponding document path to account for earlier stored-file renames. Regression checks cover restart, preview, reading, retry, download, and removal of those sources.

`README.md` documents storage compatibility and the API change. `VERSION` advances from the working baseline `0.4.19` to `1.0.0`: disabling filename mutation and removing `stored_filename` are incompatible API changes under `AGENTS.md`.

## Verification

All Python commands below use `/tmp/tomeshed-bug0045-venv/bin/python`.

| Criteria | Result | Evidence |
| --- | --- | --- |
| AC-1 | passed | `tests/browser_check_bug0050.py`: healthy footer, unreachable server, version mismatch, and recovered connection. |
| AC-2 | passed | `tests/browser_check_preview_controls.py`: resting opacity, hover regions, keyboard focus, disabled boundaries, mouse, pen, touch, and unchanged hitbox geometry. Visual inspection of light and dark PDF content in both themes; screenshots under `/tmp/tomeshed-bug0050-browser/`. |
| AC-3 | passed | `tests/browser_check_bug0050.py`, `tests/browser_check_reader_header.py`, `tests/browser_check_reader_panel.py`, and `tests/browser_check_file_workflows.py`: top-bar placement, original and converted formats, keyboard access, minimized panel, PDF/EPUB download bytes, and layouts down to 320 pixels. Independent reviewer checked desktop widths 1110, 1200, 1280, and 1440 for overlap and menu visibility. |
| AC-4 | passed | Browser checks confirm read-only original filename metadata, editable Title/Author, and no stored-filename editor. Backend checks confirm HTTP 409 without source or record mutation; anonymous rename requests remain unauthorized. |
| AC-5 | passed | `tests/test_file_workflows.py`: concurrent same-name PDF/EPUB imports with distinct bytes and UUID source names, URL type correction, watched-folder registration, stable paths after metadata edits, and legacy restart/retry/preview/reader/removal compatibility. Existing multipart import tests remain covered by `tests/test_documents.py`. |
| AC-6 | passed | Backend and browser checks compare original bytes and suggested filenames for PDF/EPUB downloads, including spaces and Unicode. Bulk checks verify duplicate entry suffixes, safe names for historical metadata, and reserved manifest naming. Existing export authorization and converted-format checks pass. |

**passed** — Original regression checks failed before their fixes: the browser check found the healthy connection label; the preview check found zero resting opacity; the backend check rejected the user filename as a UUID basename. The same regression checks pass after the fixes.

**passed** — Complete Python suite: `/tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_*.py` reported `84 passed in 133.76s` after the declared dependencies were installed.

**passed** — Focused browser checks: `tests/browser_check_preview_controls.py`, `tests/browser_check_reader_header.py`, `tests/browser_check_reader_panel.py`, `tests/browser_check_reader.py`, `tests/browser_check_file_workflows.py`, and `tests/browser_check_bug0050.py`.

**passed** — `node --check static/app.js`, `node --check static/reader.js`, and `git diff --check`. No temporary debug instrumentation remains in the changed implementation or checks.

**passed** — Independent agent review found no actionable defects in the final UI and storage implementation. The reviewer also inspected preview screenshots and checked desktop toolbar/menu geometry and keyboard behavior.

The first broad Python run reported 66 passed and one failed because the local virtual environment lacked the declared `docling` dependency. Installing `requirements.txt` resolved that environment gap. The failed `tests/test_documents.py::test_real_docling_json_pdf_and_epub_pagination` check then passed, and the import browser check passed with real conversion available.

**not_run** — Container build and deployment. The requested fix was implemented and verified in the repository; no running deployment or persistent library volume was changed.
