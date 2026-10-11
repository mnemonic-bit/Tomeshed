# Bug 0041 — Header uses text Add Document and always shows Imports

**Status:** Open

## Observed behavior

The main page header shows a rectangular `Add document` text button and an `Imports` button even when no document is being imported. The two text buttons take more header space than the requested compact actions.

## Reproduction

1. Open the library when there are no `pending` or `processing` import jobs. Observe the `Add document` and `Imports` text buttons in the header.
2. Start importing a document. Observe that `Imports` remains in the header and its count reflects active jobs.
3. Wait until every import finishes or fails. Observe that `Imports` remains visible even though no import is active.

## Expected behavior

- Replace the header's `Add document` text button with a green circular button containing a plus sign. Keep a clear accessible name such as `Add document`, visible keyboard focus, and a touch-sized target. Activating it must still provide the available ways to add a document, including local file upload and URL import.
- Show the `Imports` header button only while at least one import job is `pending` or `processing`. Show the active-job count while it is visible. Hide the button when the last active job reaches a terminal state, including `ready`, `ready_with_warning`, or `failed`.
- Keep failed-job details and retry actions reachable when no active import remains. If the Imports drawer is already open when its header button becomes hidden, keep a usable dismissal path and return focus to a visible control on close.
- Update the button's visibility after an upload starts, after import-state events, after cancellation or failure, and after reloading the library page.

## Diagnosis

`templates/index.html` always renders both header buttons. `static/app.js` updates `#activeImportCount` from `pending` and `processing` jobs in `loadImportJobs()`, but does not use that count to hide `#importsButton`. The Imports drawer also contains the URL import form and failed-job retry controls, so the import interface needs another entry point when the header button is hidden. Feature 0002 currently requires `pending`, `processing`, and `failed` jobs in the drawer; that job visibility requirement remains relevant even if the header button is conditional.

## Resolution

Pending implementation.

## Verification

**not_run** — This documentation-only report does not change the header. Verify the circular plus button and its accessible name at desktop and narrow widths. Check Imports visibility and count with zero, one, and multiple active jobs; transitions to each terminal state; page reload; and import-state events. Check file and URL import entry points, failed-job retry access, drawer dismissal, and keyboard focus after the last active job finishes.
