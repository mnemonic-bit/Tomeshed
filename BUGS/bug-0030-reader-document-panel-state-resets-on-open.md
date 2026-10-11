# Bug 0030 — Reader document panel state resets on open

**Status:** Resolved in `0.4.2`

## Observed behavior

The document info panel on the left side of the full reader opens expanded every time a document is opened. If a user minimizes the panel, closes the reader, and opens the same or another document, the panel is expanded again.

## Reproduction

1. Open a document in the full reader and select `Minimize document info`.
2. Close the reader and reopen the same document. Observe that the document info panel is expanded.
3. Minimize the panel again, close the reader, and open a different document. Observe that the panel is expanded.

## Expected behavior

- Keep one document info panel state for the reader across document opens while the library page remains loaded. The state is shared by all documents, rather than stored per document.
- If the user last minimized the panel, open the next document with the panel minimized and `Restore document info` available. If the user last restored the panel, open the next document with the panel expanded.
- Start with the panel expanded until the user changes its state. Opening or closing a document must not change that choice.
- Preserve the current reader behavior that keeps the reading location stable when the panel is minimized or restored. Keep the restore control reachable by keyboard and touch.

## Diagnosis

`static/reader.js` applies the minimize or restore action through `setPanelMinimized()`, but the chosen state is held only in the current reader view. `open()` unconditionally sets `panel.hidden = false` and hides `readerPanelRestore` for every document. `close()` discards `current` without retaining the panel's state for the next open. Bug 0021 established the panel and its in-view minimize and restore behavior; it did not require state to carry across reader opens.

## Resolution

`static/reader.js` now stores `panelMinimized` outside the per-document `current` reader object. `setPanelMinimized()` updates the shared state after a minimize or restore action. `open()` applies the shared state to the document panel and restore control. `close()` leaves the state intact. The panel starts expanded on a new library page.

## Verification

**passed** — Before the fix, `.venv/bin/python tests/browser_check_reader_panel.py` exited with code 1 at the check that reopens the same document after minimization. The panel was expanded.

**passed** — After the fix, `.venv/bin/python tests/browser_check_reader_panel.py` exited with code 0. The check covers the initial expanded state, reopening the same document while minimized, restoring by keyboard, sharing expanded and minimized states across documents, touch restore after reopening, and the existing reading-position and focus behavior.
