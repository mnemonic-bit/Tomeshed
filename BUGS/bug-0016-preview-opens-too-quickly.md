# Bug 0016 — Preview opens during incidental pointer movement

**Status:** Resolved in `0.2.14`

## Observed behavior

Moving a mouse or pen over a document thumbnail immediately opens the preview bubble. The bubble shows document content and can cover neighboring results after an accidental pointer pass.

## Reproduction

Move the pointer across a document thumbnail toward another control without stopping. Observe the preview bubble open as soon as the pointer moves within the thumbnail.

## Expected behavior

Open the preview only after at least 800 ms of uninterrupted hover over a document thumbnail. Cancel the pending open when the pointer leaves, the card becomes hidden, the user begins dragging, or the reader opens. Do not fetch preview content before the dwell completes. Once open, keep the current pointer bridge and closing behavior.

## Diagnosis

`static/app.js` calls `tomeshedPreview.open` on every qualifying `pointermove`. `static/preview.js` opens the bubble and starts loading immediately; it has no hover timer. Feature 0004 requires hover opening but does not define a dwell.

## Resolution

`static/preview.js` starts one 800 ms timer when a mouse or pen first moves over a thumbnail. Further movement within the same thumbnail updates the pointer position without restarting the timer. The timer opens the preview only while the card remains visible, the pointer remains over the thumbnail, and the reader is closed. Pointer exit, pointer down, drag start, card refresh, and reader opening cancel a pending timer. The existing preview bubble pointer bridge and close behavior remain active after opening.

## Verification

**passed** — `PYTHONPATH=.:tests .venv/bin/python tests/browser_check_preview.py` exited with code 0. Its `hover_dwell` check observed no bubble or preview request during a short hover, after pointer exit, after hiding the card, during a drag, or after opening the reader. It measured at least 800 ms between the first hover movement and the first preview request, with one initial request despite movement within the thumbnail. The existing pointer bridge, navigation, focus, touch, and placement checks also passed.
