# Bug 0027 — Double-click flashes selection and selected cards show an Open overlay

**Status:** Resolved in `0.3.1`

## Observed behavior

Clicking a document thumbnail immediately selects it, showing a tick at the upper left and an `Open` button at the lower right. During a double-click, the first click shows those controls, the second click clears selection, and only then does the document open in the reader. The `Open` button also remains visible after an ordinary single-click selection, although it should not appear on the thumbnail.

## Reproduction

1. Open a library with an unselected document card.
2. Click its thumbnail once. Observe the selection tick and the lower-right `Open` button.
3. Double-click an unselected thumbnail slowly enough to see the first click. Observe the tick and `Open` button appear before the reader opens, then disappear on the second click.
4. Double-click an already selected thumbnail. Observe that selection changes before the reader opens.

## Expected behavior

- Do not render an `Open` tag or button over a document thumbnail, whether the document is selected or unselected. Keep the selection tick for a confirmed selection.
- For mouse and pen input, defer the single-click selection change until the supported double-click interval has passed without a second click on the same thumbnail. If a double-click is recognized, cancel the pending selection change and open the reader directly. A double-click must not briefly change the tick, selected border, `aria-pressed`, or the selected-document count.
- After a single click is confirmed, toggle that document's selection once. With Bug 0026's multi-document selection, a single click on another thumbnail adds it without clearing previous selections; pending clicks on different thumbnails must not cancel each other.
- Keep keyboard Space available for selection and Enter for opening without an artificial mouse-click delay. Keep a touch-accessible way to open a document outside the thumbnail overlay, while a short tap can select it. Opening the reader must preserve unrelated selections as required by Bug 0026.

## Diagnosis

`static/app.js:301-307` calls `selectDocument()` synchronously for every `click` and separately opens the reader on `dblclick`. Browser double-clicks dispatch click events before the double-click event, so both selection transitions are visible before the reader opens. `static/app.js:196-209` reveals `.document-selected-open` whenever the card is selected. `static/app.js:323-327` creates that `Open` button inside the thumbnail, and `static/styles.css:83-84` positions it at the lower right. `openReader()` in `static/app.js:297-300` also clears the current selection. Bug 0020 established these single-selection and touch-opening behaviors; this report changes the click timing and removes the thumbnail overlay. Bug 0026 separately expands selection to multiple documents.

## Resolution

`static/app.js` now waits 500 ms before applying a mouse or pen thumbnail click. A second click and its `dblclick` event cancel the pending change before the reader opens. Each card owns its pending timer, so clicks on different cards can both select. Keyboard Space and touch tap toggle selection immediately; Enter opens the reader immediately. `#selectionActions` now provides an `Open` button and a document chooser outside the cards. One selected document is chosen automatically; two or more require an explicit choice. The toolbar fetches the chosen document at opening time, including when the selection was made on another catalog page. Opening the reader preserves the current selection.

`static/styles.css` removes the selected thumbnail overlay rule and gives the toolbar chooser and `Open` button 44 px touch targets. Document captions again contain only the title, as required by Bugs 0013 and 0019. `tests/browser_check_double_click.py` records the tick, border, `aria-pressed`, and count throughout double-clicks on selected and unselected cards. It also checks deferred mouse and pen clicks, independent clicks on two cards, immediate keyboard actions, and the toolbar `Open` action.

## Verification

**passed** — Source inspection confirms the immediate `click` selection, separate `dblclick` opening, and selected-only `Open` overlay. The existing `tests/browser_check_selection.py` checks final selection after a double-click but does not check the intermediate visual state.

**passed** — Before the fix, `.venv/bin/python tests/browser_check_double_click.py` failed because `.document-selected-open` existed on every card. The existing `.venv/bin/python tests/browser_check_selection.py` failed after the timing change because it assumed immediate mouse selection. The updated checks passed after the fix.

**passed** — `.venv/bin/python tests/browser_check_double_click.py` passed. Its mutation records showed no selection state change through either double-click. `.venv/bin/python tests/browser_check_selection.py` passed, including touch selection and toolbar `Open`, multi-document selection, reader, Favorite, and preview interactions. `.venv/bin/python tests/browser_check_documents.py` passed and `.venv/bin/python tests/browser_check_preview.py` reported all 15 checks passed after those tests were updated to use the toolbar `Open` action. `node --check static/app.js` and `git diff --check` exited with code 0.

**passed** — Review follow-up: the first implementation put `Open` under each cover, conflicting with the title-only captions in Bugs 0013 and 0019. The updated `tests/browser_check_double_click.py` failed before the follow-up on its caption-only assertion. The toolbar now opens one selected document directly and requires a document choice for multiple selections. The browser checks assert title-only captions, touch opening, choice among multiple documents, opening a selected document from another catalog page, and selection preservation.
