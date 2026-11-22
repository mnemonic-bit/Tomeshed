# Bug 0049 — Import refresh loses bookshelf focus

**Status:** Resolved in `0.5.0`.

## Observed behavior

Feature 0009 independent review reproduced loss of keyboard focus when an import event refreshes the catalog while `.bookshelf-card-open` has focus. After one bubbling URL paste to a controlled DoclingDocument JSON server, keyboard focus moved from the bookshelf control to `BODY` while the import job was processing.

## Reproduction

1. Create a bookshelf visible in the catalog.
2. Focus the bookshelf open control.
3. Paste a supported document URL.
4. Wait for the import event to refresh the catalog.
5. Inspect the active element.

## Expected behavior

Feature 0009 AC-08 requires import completion to preserve keyboard focus. The matching bookshelf control retains focus after the catalog refresh when the bookshelf remains visible.

## Diagnosis

`static/app.js` `loadCatalog` captures focus only through `closest('.document-card')`. The catalog refresh replaces bookshelf cards without capturing or restoring the bookshelf control. The reviewer reproduced the behavior with an independent Chromium check.

## Resolution

`static/app.js` `loadCatalog` now captures the focused document or bookshelf card by its stable catalog key and restores the matching control after replacement with `preventScroll`. `showImports` cancels existing previews, and the document/bookshelf preview focus timers check drawer visibility both when scheduled and when executed. The paste browser check covers focused bookshelf and document controls through import completion and an additional one-second wait.

## Verification

`failed`: the independent browser check observed `document.activeElement` change from `.bookshelf-card-open` to `BODY` after URL-paste registration and the resulting SSE catalog refresh. The frontend builder is adding a regression assertion before completing the correction.

`passed`: `/tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_paste_url.py` exited 0 on the final source. Both catalog control focus cases passed, alongside reader focus/position checks. The reviewer independently repeated the bookshelf paste scenario and observed `.bookshelf-card-open` retain focus through terminal import state.

`passed`: `/tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_preview_dismiss.py` and `/tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_bookshelf_preview.py` exited 0. Existing keyboard previews remain usable with Imports closed.
