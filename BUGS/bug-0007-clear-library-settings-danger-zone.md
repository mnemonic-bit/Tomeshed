# Bug 0007 — Clear Library belongs in administrator Settings

**Status:** Resolved in `0.2.5`

## Observed behavior

The library heading contains `Clear library` for administrators. Settings has no Danger Zone. The action calls `/api/library/clear/preview` and then `/api/library/clear` after a confirmation. Both routes already reject a non-administrator with HTTP 403.

## Reproduction

Sign in as an Administrator and open the library and Settings. Find `Clear library` beside the library heading; find no Danger Zone in Settings. Sign in as a normal user and confirm that the action is absent.

## Expected behavior

Show `Clear library` only in an Administrator-only Danger Zone in Settings. Keep the existing preview, confirmation, stale-preview protection, and server-side role check. Show the result or error in Settings. A normal user must see neither the Danger Zone nor the action; direct API calls must still return HTTP 403.

## Diagnosis

`templates/index.html` places `bulkClearButton` in `.library-heading`; `static/app.js` binds its action there. `file_workflows.py` already enforces the role on both clear routes. VDL puts its destructive history action in an administrator-only Danger Zone in `VDL/templates/index.html`.

## Resolution

Moved `Clear library` from the library heading to an administrator-only Settings Danger Zone and added a matching navigation entry. Settings search finds the action for `deletion`. The browser action retains the preview, confirmation, and token submission. It now reports success and errors in Settings. Both clear routes still check the administrator role.

## Verification

**passed** — `.venv/bin/python tests/browser_check_file_workflows.py` failed before the change because the clear button remained in the library heading. After the change, the same command exited with code 0. The browser check covered Settings placement and search, confirmation cancellation, a simulated HTTP 409 shown in Settings, successful clearing, normal-user visibility, and HTTP 403 from both clear routes for a normal user.

**passed** — `PYTHONPATH=. .venv/bin/pytest -q tests/test_file_workflows.py::test_bulk_stale_cleanup_retry_and_path_boundary` exited with code 0. The server check submitted a preview token after the library changed and received HTTP 409.
