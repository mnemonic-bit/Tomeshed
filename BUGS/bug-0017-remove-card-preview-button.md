# Bug 0017 — Document cards expose an unnecessary Preview button

**Status:** Resolved in `0.2.15`

## Observed behavior

Every ready document card has a visible `Preview` button below its thumbnail, even though pointer hover over the thumbnail already opens the preview bubble.

## Reproduction

Open a library with a ready PDF or EPUB. Observe the `Preview` button and hover over its thumbnail to open the same preview.

## Expected behavior

Remove the Preview button from document cards. Pointer hover must still open the preview after the dwell in Bug 0016. Keyboard focus on the thumbnail should open the preview after the same dwell, and touch press-and-hold should open it without an extra Preview button. The preview bubble must keep its location, paging, and close controls, and opening it must not update reading progress.

## Diagnosis

`static/app.js` creates `.document-preview-action` for ready documents and also binds thumbnail `pointermove` to the same preview. `static/preview.js` uses that button to store expanded state and restore focus. Feature 0004's labelled Preview action and AC-05 require revision when the visible card button is removed.

## Proposed resolution

Remove the per-card button and give the preview controller the thumbnail as its expanded-state and focus-return anchor. Prevent the touch press-and-hold gesture from also selecting or opening the document.

## Resolution

Removed the card's `Preview` button. The thumbnail now carries `aria-controls` and `aria-expanded`. Keyboard focus and touch press-and-hold open the preview after 800 ms; a short tap opens the reader. Closing a preview opened by keyboard or touch returns focus to the thumbnail without reopening the preview. Updated Feature 0004 and the browser checks for the thumbnail interaction.

## Verification

**passed** — `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_preview.py` checked that cards have no separate `Preview` button, mouse hover, keyboard focus, and touch hold open and close the bubble, focus returns to the thumbnail, a short tap opens the reader, and preview interactions leave saved progress unchanged.

**passed** — `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_organization.py` checked that preview leaves reading state and progress unchanged alongside the organization flows.

**passed** — `PYTHONPATH=. .venv/bin/pytest -q` completed with 70 passed tests.

**passed** — `node --check static/app.js`, `node --check static/preview.js`, and `git diff --check` completed without errors.
