# Bug 0001 — Concurrent PDF page requests crashed the server

**Status:** Resolved and deployed in `0.1.1` on 2026-10-10.

**Severity:** High

## Observed behavior

Opening an imported PDF sometimes showed an image decoding error in the browser. The Tomeshed server stopped serving requests while the reader loaded page images.

## Reproduction

1. Import two PDFs with multiple pages.
2. Request their reader page images concurrently, as the browser does when it opens a PDF.
3. Observe that at least one request closes without an HTTP response and Podman restarts the server.

At the `0.1.0` baseline, all six page images from the two imported PDFs returned valid PNGs when requested sequentially. A concurrent request for those six images raised `RemoteDisconnected`; Podman then reported one container restart and no out-of-memory kill.

**Expected:** Every authorized page request returns a decodable PNG, and the server remains available.

## Diagnosis

The reader and preview called `pypdfium2` from Flask request threads without a shared lock. The [pypdfium2 threading documentation](https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading) states that simultaneous PDFium calls can crash or corrupt a process, even when the calls use different documents. The concurrent request failure and the successful sequential requests match that constraint.

## Resolution

`reader_service.py` defines `PDFIUM_LOCK`. The PDF reader and preview hold that lock while opening, reading, rendering, encoding, and closing PDFium documents. `tests/test_reader.py::test_concurrent_pdf_pages_do_not_enter_pdfium_together` exercises concurrent authenticated page requests and detects overlapping PDFium use.

## Verification

- `passed`: The regression test failed before the lock and passed after it was added.
- `passed`: The PDF reader and preview tests selected for the fix passed (`3 passed`).
- `passed`: After deployment, two rounds of six concurrent page requests returned valid PNGs. `/api/health` returned HTTP 200 and the replacement container reported zero restarts.
