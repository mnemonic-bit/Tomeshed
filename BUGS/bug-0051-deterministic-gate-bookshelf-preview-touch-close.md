# Bug 0051 — Bookshelf preview touch Close check races inertial scrolling

**Status:** Resolved locally in `0.5.1`; awaiting a GitHub Actions rerun

**Baseline:** Local investigation on commit `15567a3c86b210a9feef293de2df216193b63261`, version `0.5.0`, on 2026-11-22. The failing CI revision was not supplied.

## Observed behavior

The user reports that the Deterministic gate exits with code 1 in `tests/browser_check_bookshelf_preview.py:275`. After tapping `#bookshelfPreviewClose`, the check finds `#bookshelfPreviewBubble` still visible.

The supplied log reports `84 passed in 20.07s`, successful container lock resolution for `linux/amd64` and `linux/arm64`, and a passed Feature 0001 browser check before the failure. Those results do not establish that the complete gate passed.

The failure is intermittent locally. An isolated mobile reproduction failed at the same post-Close assertion. Event instrumentation reproduced the visible preview in three of six trials.

```text
File "tests/browser_check_bookshelf_preview.py", line 275, in main
    assert phone.locator('#bookshelfPreviewBubble').is_hidden()
AssertionError
Error: Process completed with exit code 1.
```

## Reproduction

Run `TOMESHED_TEST_PYTHON=python TOMESHED_LOCK_PYTHON=python CONTAINER_ENGINE=docker ./tests/run-all.sh` in the CI environment described by `.github/workflows/validation.yml`.

For focused reproduction, run the Python interpreter with the application dependencies, Playwright, and Chromium installed against `tests/browser_check_bookshelf_preview.py`. The mobile section creates a 390 × 750 touch context, holds the Long shelf cover to open its preview, swipes the preview grid, taps Close, and immediately asserts that the bubble is hidden.

The command used locally was:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_bookshelf_preview.py
```

To isolate the failure, retain the test's temporary server, administrator login, 12 seeded documents, Long shelf creation, and mobile section at lines 246–277. Omit the desktop preview scenarios and recipient access checks. Repeat the mobile section with a fresh touch context for each trial. The reduced sequence reproduces without the earlier desktop interactions.

The triggering sequence in the existing test is:

1. Hold the bookshelf cover until the preview opens, then release the touch.
2. Start a touch at 70% of the preview grid height.
3. Send four upward moves of 30 px each, separated by 30 ms, then release the touch.
4. Wait only for `#bookshelfPreviewGrid.scrollTop > 0`.
5. Tap `#bookshelfPreviewClose` while inertial scrolling can still be active.
6. Observe the failed hidden-state assertion. Repeat because the timing changes between runs.

## Expected behavior

After the grid finishes scrolling, tapping Close dismisses the bookshelf preview. A subsequent short tap on the bookshelf cover opens the bookshelf detail dialog. The deterministic gate verifies both behaviors without timing-dependent failures. The scrolling assertion still verifies that the touch gesture moved the grid.

## Diagnosis

The browser check waits for scroll movement rather than scroll completion. `scrollTop > 0` at line 272 is already true during the swipe, so the check can immediately tap Close while Chromium continues inertial scrolling after touch release.

In failing instrumented trials, Chromium delivers `pointerdown`, `touchstart`, `pointerup`, and `touchend` to `#bookshelfPreviewClose` but emits no `click`. Scrolling ends just after the tap. `static/bookshelves.js:439` binds Close to `click`, so `closePreview(true)` is not invoked. The bubble remains visible after another 400 ms; waiting longer for a hidden-state assertion after that tap does not recover the missing click.

One failed trial recorded the following sequence. Times are milliseconds relative to the grid swipe's touch release:

| Time | Event | Observation |
| --- | --- | --- |
| 0 | Grid `touchend` | `scrollTop = 105`; bubble visible |
| +44 | Grid `scroll` | `scrollTop = 141`; scrolling continues |
| +61 | Close touch begins and ends | `scrollTop = 153`; no `click` follows |
| +78 | Grid `scrollend` | `scrollTop = 164`; bubble still visible |
| After a further 400 ms | Hidden-state observation | Bubble still visible |

In passing trials, `scrollend` precedes the Close tap, Chromium emits `click`, and the bubble's `hidden` attribute becomes true. An attribute observer found no hide-and-reopen sequence in the failing trials. A controlled probe that waited for the grid's `scrollend` before tapping Close produced the expected dismissal.

The evidence supports a test synchronization defect: a tap during active inertial scrolling can stop scrolling without activating Close. The event trace rules out delayed hidden-state propagation and immediate reopening as explanations for the reproduced failure. The exact failing CI browser build is unknown; the local reproduction used Python 3.11.2, Playwright 1.63.0, Flask 3.1.3, and cached Chromium revision 1243. The workflow configures Python 3.12 and installs Playwright from the range in `requirements-dev.txt`.

`tests/run-all.sh` uses `set -euo pipefail` and runs browser checks sequentially. This assertion aborts the gate before later browser checks and the final container smoke check.

## Resolution

`tests/browser_check_bookshelf_preview.py` now registers a one-shot `scrollend` listener on the preview grid before sending the swipe. The listener records completion in `data-touch-scroll-complete`, so completion remains observable if scrolling finishes before Playwright starts waiting. After confirming that the gesture moved the grid, the check waits up to 2.5 seconds for scroll completion before tapping Close.

After the Close tap, the check waits up to 2.5 seconds for the hidden state. The real touch gesture, positive-scroll assertion, subsequent short tap opening the shelf detail dialog, and recipient access checks remain in place. The listener removes itself when `scrollend` fires. `VERSION` increments from `0.5.0` to `0.5.1` for this test synchronization fix.

Acceptance:

- **AC-01:** The isolated mobile sequence dismisses the preview after completed scrolling in 20 consecutive fresh touch contexts.
- **AC-02:** `tests/browser_check_bookshelf_preview.py` passes, including the subsequent short tap opening the detail dialog and the recipient access checks.
- **AC-03:** The complete Deterministic gate passes in GitHub Actions, including later browser checks and the container smoke check.

## Investigation verification

**failed** — User-supplied CI log: the assertion at `tests/browser_check_bookshelf_preview.py:275` fails and the job exits with code 1.

**passed** — The unmodified focused browser command above exited with code 0 and printed `bookshelf preview: passed` once. A single pass does not exclude this intermittent defect.

**failed** — A temporary reduced probe, run with `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python /tmp/tomeshed-bug0051-repeat.py`, failed on its first mobile trial at the post-Close hidden-state assertion. The probe compiled a reduced copy of the existing test in memory; tracked test and application files were unchanged.

**failed** — Six mobile trials with event instrumentation and the original tap timing produced three visible previews and three hidden previews after Close. All three failures remained visible after another 400 ms. Instrumentation recorded the missing `click` and the scrolling timeline described above.

**inconclusive** — An initial control registered its `scrollend` listener after the swipe. A repeated run timed out because scrolling could finish before listener registration. This control cannot establish reliable synchronization.

**passed** — After registering `scrollend` observation before the swipe and waiting for completion before tapping Close, six of six fresh touch contexts hid the preview immediately and kept the preview hidden after another 400 ms. The temporary probe command was `BUG0051_MODE=settled PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python /tmp/tomeshed-bug0051-events.py`. A wrapper checked all six observations and exited with code 0. This experiment supports the proposed correction; it does not establish that a permanent fix or the complete gate passes.

**not_run** — During the initial investigation, the complete local gate and a GitHub Actions rerun were outside the requested analysis scope. The temporary investigation probes and logs were removed. The initial documentation-only change left `VERSION` at `0.5.0`.

## Fix verification

**passed — AC-01:** `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python /tmp/tomeshed-bug0051-verify-mobile.py` exited with code 0 after 20 consecutive fresh touch contexts passed. The temporary harness compiled a reduced in-memory copy of the current browser check, retaining its setup, seeded Long shelf, and unchanged corrected mobile section. Every trial exercised real CDP touch scrolling, Close dismissal, and a subsequent short tap opening `#bookshelfDialog`. The implementation agent removed the harness after verification.

**passed — AC-02:** The implementation agent and independent review agent each ran `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_bookshelf_preview.py`. Both runs exited with code 0 and printed `bookshelf preview: passed`, including the subsequent short tap and recipient access checks.

**passed** — Independent review found no issues in listener registration timing, preservation of early completion, timeout behavior, listener cleanup, or retained touch and access checks. `git diff --check` exited with code 0.

**passed** — `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_*.py` exited with code 0: `104 passed in 240.68s`.

**passed** — `PIP_DEFAULT_TIMEOUT=60 PIP_RETRIES=1 TOMESHED_LOCK_PYTHON=/tmp/tomeshed-bug0045-venv/bin/python tests/container/check-lock.sh` exited with code 0 and printed `Container lock resolves for linux/amd64 and linux/arm64`. The first attempt with the default network timeout failed during a package download; the retry passed without dependency changes.

**passed** — `CONTAINER_ENGINE=podman tests/container/smoke.sh --build` built `localhost/tomeshed:smoke` and exited with code 0. Both smoke phases passed, including health/version verification, PDF/EPUB imports and preserved sources, reader/preview concurrency, and saved reading position after container recreation. The smoke check used its own temporary volumes.

**passed** — All 25 `tests/browser_check*.py` scripts were exercised with the same interpreter. Twenty-four scripts passed, including the corrected bookshelf preview check. The root agent ran the page-shell check and 22 other scripts; the implementation and independent review agents each ran the corrected bookshelf preview check. The only failing script is recorded below.

**failed** — Broader browser validation and an independent rerun both stopped at `tests/browser_check_bookshelves.py:258`, a saved reader-position assertion after server restart. That check was unchanged by this fix. [Bug 0052](bug-0052-bookshelf-reader-position-after-restart.md) records the separate failure and its unconfirmed cause. The complete local gate cannot be reported as passed.

**not_run — AC-03:** A GitHub Actions rerun requires the changed revision to reach the workflow. The complete Deterministic gate has not been reported as passed in CI for this fix.
