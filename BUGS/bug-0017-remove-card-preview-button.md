# Bug 0017 — Document cards expose an unnecessary Preview button

**Status:** Open

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

## Verification

**not_run** — Documentation only. Check that no card shows Preview; mouse hover, keyboard, and touch can still open and close a preview; focus returns to the trigger; no preview interaction changes saved progress.
