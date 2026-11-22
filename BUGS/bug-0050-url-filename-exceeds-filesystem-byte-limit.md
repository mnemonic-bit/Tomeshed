# Bug 0050 — URL filename exceeds the filesystem byte limit

**Status:** Resolved in `0.5.0`.

## Observed behavior

Independent review registered a URL whose basename was the percent-encoded character `書` repeated 100 times. The URL was within the 4096-character URL limit and served valid DoclingDocument JSON. Registration returned HTTP 202, but the job failed with `[Errno 36] File name too long`. Cleanup logged the same filesystem error.

## Reproduction

1. Configure a controlled HTTP server to return valid DoclingDocument JSON.
2. Register a URL with a basename formed by percent-encoding `書` repeated 100 times.
3. Wait for the import job to finish.
4. Inspect the job error and source filename.

## Expected behavior

Feature 0009 AC-05 requires a safe filename with the detected source extension. A valid source from this permitted URL imports successfully with a filename within the filesystem byte limit and a `.json` suffix. Export preserves the source bytes.

## Diagnosis

`file_workflows.url_filename` limits the decoded basename to 240 characters. The reproduced basename has 300 UTF-8 bytes, exceeding the filesystem component limit before the downloaded source can be stored.

## Resolution

`file_workflows.url_filename` now truncates the decoded basename to 240 UTF-8 bytes and removes an incomplete final codepoint. The bound reserves space for the detected `.pdf`, `.epub`, or `.json` extension. `tests/test_paste_url.py` adds `test_multibyte_url_filename_preserves_detected_extension_and_source`, using a misleading `.pdf` URL with 100 CJK characters and a valid JSON response.

## Verification

`failed`: an independent controlled-response test observed HTTP 202 followed by a failed job with `[Errno 36] File name too long` for the valid JSON source. A durable backend regression will record the corrected behavior.

`passed`: `/tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_paste_url.py -k multibyte` reported `1 passed, 32 deselected` in 12.05 seconds. The assertion verifies the detected `.json` suffix and exported source bytes. Independent re-review passed: the reviewer ran `/tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_paste_url.py -k 'multibyte or transfer_limit or account_job or restart_reconciliation'` and recorded `7 passed, 26 deselected` in 45.90 seconds. No unresolved filename finding remains.
