# Bug 0052 — Bookshelf browser check fails its reader-position assertion after restart

**Status:** Resolved locally in `1.0.1`; awaiting a GitHub Actions rerun

**Baseline:** Observed while verifying Bug 0051 in the working tree based on commit `15567a3c86b210a9feef293de2df216193b63261`, with `VERSION` set to `0.5.1`.

**Fix baseline:** The requested fix started on 2026-11-22 at commit `37748e29a7501a12036b2a2e62664a4eafa1d72f`, with `VERSION` set to `1.0.0`. The implementation agent owns the correction and regression checks; an independent agent owns review and verification.

## Observed behavior

`tests/browser_check_bookshelves.py` exits with code 1 at line 258 while checking saved reader positions after restarting its temporary server. An independent review agent repeated the command and observed the same assertion failure. The check aborts before its remaining scenarios.

```text
File "tests/browser_check_bookshelves.py", line 258, in main
    assert page.locator('#readerPosition').inner_text()==owner_labels[title]
AssertionError
```

## Reproduction

Run with the application dependencies, Playwright, and Chromium installed:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_bookshelves.py
```

The check records reader-position labels for PDF, EPUB, and Docling bookshelf members, closes and reopens the reader, reloads the browser page, and restarts the temporary server. The observed assertion failure occurs in the loop that reopens each format after the restart and compares `#readerPosition` with the earlier label.

## Expected behavior

After the server restarts, opening a bookshelf member restores the owner's saved reading position. The browser check compares the restored position after the reader has finished updating its displayed position.

## Diagnosis

The failure is an EPUB rendering race in `static/reader.js`. The reader restored the saved locator and calculated its progress label after one animation frame, without waiting for embedded EPUB images to load. A late image changed the scroll range after the progress calculation. The label could remain incorrect after the image finished loading because image loading did not refresh the label.

An independent trace identified the failing document as `EPUB Book`: the saved label was `Location 2 · 94%`, while the restored label was `Location 2 · 95%`. The restored label remained at 95% after another 500 ms. A passing instrumented run recorded `scrollTop = 800`, `scrollHeight = 1574`, and `clientHeight = 726`. The fixture contains a 4 × 4 image; omitting its height during restoration changes the scroll range enough to explain the one percentage point difference.

A controlled probe delayed the EPUB image resource response by 300 ms after server restart and reproduced the exact label mismatch. The permanent delayed-image regression also failed against the unchanged reader. These results establish a reader layout defect rather than an assertion that only needs more waiting. PDF, EPUB, and Docling label comparisons remain exact.

## Resolution

The reader now waits for all embedded EPUB image decode promises to settle before restoring the saved locator and calculating progress. Failed images do not prevent the EPUB from opening. The existing generation check prevents an opening operation from restoring an old document after the reader closes or another document opens. PDF image failure behavior remains unchanged.

`tests/browser_check_bookshelves.py` adds a delayed-image regression after server restart. The check holds the image response and waits two animation frames before asserting that the reader still displays `Opening…`. After releasing the image response, the check requires the exact saved progress label and a restored scroll position within one pixel of the original position. Saved-locator comparisons run after the next reader starts, which waits for preceding progress writes. Additional scenarios cover a failed image and closing an EPUB with a pending image before opening Docling content. Position assertions now report the document title and actual and expected labels.

`VERSION` increments from `1.0.0` to `1.0.1`.

## Verification

**failed** — The root agent's browser validation stopped at the assertion above with exit code 1.

**failed** — The independent review agent ran the reproduction command separately and observed exit code 1 at the same assertion.

**failed** — Both implementation and independent review agents reproduced the original post-restart assertion failure with the reproduction command above.

**failed** — The permanent delayed-image regression, run against the unchanged reader with the same command, reported `('EPUB Book with delayed image', 'Location 2 · 95%', 'Location 2 · 94%')` and exited with code 1.

**failed** — The final held-image regression was also verified against the original reader. A temporary harness served `git show HEAD:static/reader.js` through a Playwright route while running the final bookshelf check. `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python /tmp/bug52-baseline-reader.py` exited with code 1 at the assertion requiring `Opening…` while the image response remained held. The harness did not modify repository source.

**passed** — `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_reader.py` exited with code 0: `6 passed in 10.05s`.

**passed** — `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_reader.py` exited with code 0. The check covered PDF close/reload/restart, EPUB images and reflow, Docling fallback, error states, and progress saves.

**passed** — `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_reader_close.py` exited with code 0.

**passed** — Both implementation and independent review agents ran `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_bookshelves.py` against the final correction. Both runs exited with code 0, including the deterministic held-image regression, exact restored label, restored scroll position, saved locator, failed-image text access, close/reopen safety, and the original restart scenarios.

**passed** — Independent source review found no remaining issues. The final regression holds the image response until explicit release and waits for preceding progress writes before comparing persisted locators.

**passed** — `git diff --check` exited with code 0.

**not_run** — The complete validation gate and GitHub Actions rerun have not been run for this fix. The VDL source tree is absent from this workspace, so the implementation agent could not inspect the prototype.
