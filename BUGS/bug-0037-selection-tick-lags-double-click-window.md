# Bug 0037 — Selection tick appears after the double-click window

**Status:** Open

## Observed behavior

The user reports that a single click on a document thumbnail does not show the selection tick until after the interval in which a second click would be recognized as a double-click. This leaves a period in which the click can no longer open the reader as a double-click, but the library still gives no visible selection feedback.

## Reproduction

1. Open the library with an unselected document thumbnail.
2. Click the thumbnail once with a mouse or pen.
3. Observe when the selection tick appears in the thumbnail's upper-left corner.
4. Compare that delay with the longest interval at which two clicks on the same thumbnail still open the reader as a double-click in the same browser and input environment. The reported behavior is that the tick appears later.

## Expected behavior

Show the selection tick as soon as the opportunity for the second click to form a double-click has expired. The app's single-click selection delay and effective double-click recognition interval should end together, without an additional period of missing feedback. A recognized double-click still opens the reader without briefly showing the tick or changing the selected count. Keyboard and touch selection retain their immediate feedback.

If the effective double-click interval varies by browser or system settings, choose and document a click handling rule that gives the earliest reliable selection feedback for each supported environment. Verify the boundary with clicks just inside and just outside the interval.

## Diagnosis

Not confirmed. `static/app.js` starts a fixed 500 ms selection timer for a mouse or pen `click` and cancels it on a second click or `dblclick`. The browser's effective double-click interval has not been measured for this report, so the reported gap and its duration remain to be reproduced.

## Resolution

Pending investigation and fix.

## Verification

**not_run** — The timing difference was reported by the user. No browser timing measurement or regression check was run for this documentation-only report. A fix should be checked by recording the first click, selection tick, second click, and `dblclick` event times across the recognition boundary, including single clicks, recognized double-clicks, mouse and pen input, and immediate keyboard and touch selection.
