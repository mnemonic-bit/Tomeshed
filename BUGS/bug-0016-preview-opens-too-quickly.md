# Bug 0016 — Preview opens during incidental pointer movement

**Status:** Open

## Observed behavior

Moving a mouse or pen over a document thumbnail immediately opens the preview bubble. The bubble shows document content and can cover neighboring results after an accidental pointer pass.

## Reproduction

Move the pointer across a document thumbnail toward another control without stopping. Observe the preview bubble open as soon as the pointer moves within the thumbnail.

## Expected behavior

Open the preview only after at least 800 ms of uninterrupted hover over a document thumbnail. Cancel the pending open when the pointer leaves, the card becomes hidden, the user begins dragging, or the reader opens. Do not fetch preview content before the dwell completes. Once open, keep the current pointer bridge and closing behavior.

## Diagnosis

`static/app.js` calls `tomeshedPreview.open` on every qualifying `pointermove`. `static/preview.js` opens the bubble and starts loading immediately; it has no hover timer. Feature 0004 requires hover opening but does not define a dwell.

## Proposed resolution

Start one cancellable hover timer on entry and open only if the pointer still rests over the same thumbnail when the timer fires. Avoid restarting the timer for every move within that thumbnail. Keep the full reader's opening separate from the hover timer.

## Verification

**not_run** — Documentation only. In a browser, cross a thumbnail in less than 800 ms and confirm no bubble or preview request. Dwell longer than 800 ms and confirm one bubble and one initial request. Check cancellation and movement into the open bubble.
