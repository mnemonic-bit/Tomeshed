# Bug 0026 — Selecting a second document clears the first selection

**Status:** Resolved in `0.3.0`

## Observed behavior

A single click on a document thumbnail marks that document as selected. Clicking a second thumbnail removes the first document's selection, leaving only the second selected. Selection therefore cannot be used to act on several documents together. Download and Remove document are available only for one document at a time in the reader's document panel.

## Reproduction

1. Open a library containing at least two documents.
2. Click the first document thumbnail once. Observe its selection tick.
3. Click the second document thumbnail once. Observe that the first tick disappears and only the second document remains selected.
4. Look for an action that downloads or removes the selected documents together. No such action is available.

## Expected behavior

- Clicking an unselected document thumbnail adds that document to the selection without clearing other selected documents. Clicking a selected thumbnail removes only that document from the selection. Touch tap and keyboard Space perform the same toggle; Enter still opens the reader. Expose `aria-pressed` and a visible selection indicator on every selected card.
- Keep selection across catalog refreshes, search, filters, sort, and numbered or endless pagination so users can select documents on different result pages. Keep a visible selected count and a **Clear selection** action. Remove a document from the selection when it is deleted or the current user can no longer access it.
- Offer actions for the selected set. **Download selected** provides the preserved original files in one ZIP archive with unambiguous filenames; documents without an available source produce an explicit result rather than a substituted generated file. **Delete selected** requires confirmation that identifies the number of documents and removes only the confirmed selection. Report each failure and the documents that remain if an action is only partly successful.
- Check access for every selected document on the server when an action runs. Keep the existing single-document Download original and Remove document paths usable. Opening a document in the reader must not silently discard the other selected documents. Favorite clicks and preview interactions must not change selection.

## Diagnosis

`static/app.js:195-218` stores selection in the scalar `selectedDocumentId`; `selectDocument()` replaces that ID whenever a different thumbnail is clicked. `updateDocumentSelection()` marks only the matching card. `static/app.js:296-305` also clears selection before opening the reader, and `static/app.js:516` clears selection when the selected card leaves the current rendered page. `tests/browser_check_selection.py:43-59` asserts the current single-selection behavior. Bug 0020 introduced that behavior intentionally; this report records the expanded requirement. `static/app.js:405-435` exposes downloads and removal for one document through its reader panel. Feature 0006 requires authorization for each export and removal and distinguishes preserved originals from Docling artifacts.

## Resolution

`static/app.js` now keeps selected document IDs in a set. Pointer click, touch tap, and Space toggle one card; Enter opens the reader without clearing selection. The library shows a selected count and Clear selection, Download selected, and Delete selected actions. Selection survives catalog queries, refreshes, and page-size changes. A status request after each catalog refresh removes IDs for deleted or inaccessible documents. Single-document reader actions remain available.

The new bulk API accepts 1–1000 distinct document IDs per request and checks each ID when the action runs:

| Endpoint | Request | Result |
| --- | --- | --- |
| `POST /api/documents/bulk/status` | `{"ids":[...]}` | `accessible_ids` and `unavailable_ids` for selection reconciliation. |
| `POST /api/documents/bulk/export/original` | `{"ids":[...]}` | A ZIP of available, authorized original files plus `manifest.json`. Each included filename contains the full document ID. The manifest lists every included file and every `unavailable` or `source_unavailable` failure, without a response header size limit. Response headers provide included and failure counts. |
| `POST /api/documents/bulk/delete` | `{"ids":[...],"confirm_count":N}` | HTTP 200 for full success or 207 for partial failure, with `removed`, per-ID `failures`, and `remaining_document_ids` for documents still accessible to the caller. A mismatched confirmation count returns 400. Deletion requires management access for each document and reports `unavailable`, `not_manageable`, `active_import`, or `cleanup_failed` where applicable. |

The browser confirms the selected count before deletion. It reconciles the confirmed IDs against `remaining_document_ids`, keeping accessible documents whose deletion failed and removing deleted or inaccessible IDs. It reports each failure with the document label when available. The browser reads export outcomes from `manifest.json` inside the ZIP, so it can report and reconcile every failure even for large selections. ZIP archives always contain `manifest.json`, including when no original source is available.

## Verification

**passed** — Before the fix, source inspection confirmed the scalar selection state, replacement on a second thumbnail click, selection clearing on page replacement and reader open, and the current single-document actions.

**passed** — The updated `tests/browser_check_selection.py` failed against the original code when clicking the second document cleared the first. After the fix, `.venv/bin/python tests/browser_check_selection.py` passed. It covers pointer, touch, Space, and Enter; selection across search, filters, sort, refresh, numbered pages, and Endless scrolling; count and clear; ZIP download; confirmed deletion; partial failure display; deletion and access revocation reconciliation; and Favorite and preview isolation.

**passed** — The new `tests/test_file_workflows.py::test_selected_bulk_originals_and_delete_report_each_result` failed against the original code with HTTP 405. After the fix, the focused test passed. It checks unique ZIP names and original bytes, missing-source manifest results, per-item access, owner deletion, confirmation validation, and partial cleanup failure reporting.

**passed** — Review follow-up: the browser check reproduced both a public document wrongly leaving selection after a denied delete and 200 missing export IDs remaining selected because the failure header exceeded 6000 characters. After the fix, the browser check passed; it verifies that the public document remains selected, all 200 export failures appear by ID, and the absent IDs leave selection. The backend test verifies the 200-entry manifest and distinct `not_manageable` and `unavailable` delete results.

**passed** — `.venv/bin/python -m pytest tests/test_file_workflows.py tests/test_catalog_pagination.py -q` reported 14 passed. `.venv/bin/python tests/browser_check_pagination.py` and `.venv/bin/python tests/browser_check_preview.py` passed. `node --check static/app.js`, `.venv/bin/python -m py_compile file_workflows.py`, and `git diff --check` exited with code 0.
