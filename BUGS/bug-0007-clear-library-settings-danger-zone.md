# Bug 0007 — Clear Library belongs in administrator Settings

**Status:** Open

## Observed behavior

The library heading contains `Clear library` for administrators. Settings has no Danger Zone. The action calls `/api/library/clear/preview` and then `/api/library/clear` after a confirmation. Both routes already reject a non-administrator with HTTP 403.

## Reproduction

Sign in as an Administrator and open the library and Settings. Find `Clear library` beside the library heading; find no Danger Zone in Settings. Sign in as a normal user and confirm that the action is absent.

## Expected behavior

Show `Clear library` only in an Administrator-only Danger Zone in Settings. Keep the existing preview, confirmation, stale-preview protection, and server-side role check. Show the result or error in Settings. A normal user must see neither the Danger Zone nor the action; direct API calls must still return HTTP 403.

## Diagnosis

`templates/index.html` places `bulkClearButton` in `.library-heading`; `static/app.js` binds its action there. `file_workflows.py` already enforces the role on both clear routes. VDL puts its destructive history action in an administrator-only Danger Zone in `VDL/templates/index.html`.

## Proposed resolution

Move the action into a Settings Danger Zone and add an administrator-only navigation entry. Preserve the existing server authorization and confirmation flow. Keep the action available through Settings search when the Administrator searches for library deletion.

## Verification

**not_run** — Documentation only. Check both roles in a browser, then call both endpoints as a normal user. Check confirmation cancellation, stale preview, success, and error feedback as an Administrator.
