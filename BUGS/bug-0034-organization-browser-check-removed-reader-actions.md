# Bug 0034 — Organization browser check uses removed reader actions

**Status:** Resolved in `0.4.6`

## Observed behavior

`tests/browser_check_organization.py` times out waiting for `#readerFinished`. Bug 0032 removed that control and `#readerStartOver` from the reader. The organization browser check still clicks both controls, so the browser sweep stops before its later checks.

## Reproduction

Run `.venv/bin/python tests/browser_check_organization.py`. The check reaches the reader-state section and times out at its `#readerFinished` click near line 345.

## Expected behavior

The organization browser check verifies per-user reading state and preview isolation through supported endpoints and the current reader UI. It completes without referring to removed reader controls.

## Diagnosis

The Bug 0032 reader header change removed the completion and reset buttons. `tests/browser_check_reader.py` was updated, but the organization browser check retained its button clicks.

## Resolution

`tests/browser_check_organization.py` now calls the authenticated `POST /api/documents/book06/finish` and `POST /api/documents/book06/start-over` endpoints. The check still verifies the reading-state transitions, preview isolation, and account separation.

## Verification

**failed** — Before the fix, the browser sweep stopped in `tests/browser_check_organization.py` at `#readerFinished`; Playwright timed out after 30 seconds.

**passed** — `.venv/bin/python tests/browser_check_organization.py` exited with code 0. All 15 reported checks passed, including `reader_state_preview_isolation`, `two_accounts`, and `restart_persistence`.
