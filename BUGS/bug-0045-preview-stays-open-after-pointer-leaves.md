# Bug 0045 — Preview stays open after the pointer leaves

**Status:** Resolved in `0.4.18`

## Observed behavior

The user reports that the document preview remains open after the mouse pointer has moved outside both the preview bubble and its originating document thumbnail. The user supplied a reliable trigger: hover until the preview opens, then click the thumbnail to select or deselect the document before moving the pointer away. An earlier report associated the failure with navigating back and forth through preview pages. Browser reproduction confirmed the selection trigger with a PDF in Chromium; other browser engines have not been checked.

## Reproduction

1. Hover over a document thumbnail until its preview opens.
2. Click the thumbnail to select the document.
3. Move the mouse pointer outside both the preview bubble and the originating card.
4. Observe that the preview remains open.
5. Repeat with a selected document, clicking the thumbnail to deselect it.

The earlier reproduction used the preview's `Previous` and `Next` controls several times before moving the pointer away. Verification must also cover that sequence.

## Expected behavior

Once the mouse pointer leaves the preview bubble and its originating card, the preview closes unless keyboard focus remains inside the card or bubble. Mouse selection and page navigation must not leave the preview open through incidental DOM focus. Keyboard users can keep the preview open while navigating its controls and dismiss it with Escape or by moving focus outside.

## Diagnosis

`static/preview.js` retained the preview whenever `document.activeElement` was inside the originating card or bubble. A mouse click focuses the thumbnail, so the pointer-exit checks treated mouse focus as keyboard focus.

The browser probe confirmed that selecting and deselecting left the connected thumbnail focused with `:focus-visible` false. The preview remained visible with the pointer at `(0, 0)`, outside both surfaces. Blurring only the thumbnail before another pointer move closed the preview. Selection updates the existing card, so a detached originating card did not explain this reproduction. Navigation-only checks passed against the original implementation; the earlier page-navigation report remains unconfirmed.

## Resolution

`static/preview.js` now shares a `hasKeyboardFocus()` predicate across pointer movement, viewport exit, and placement rechecks. The predicate retains the preview only when the focused element is inside the originating card or bubble and matches `:focus-visible`, consistent with keyboard preview opening. Mouse clicks can still select documents and navigate pages without pinning the preview open. The separate focus-departure and touch-dismissal handlers retain their existing behavior.

`tests/browser_check_preview_dismiss.py` covers selection and deselection, viewport exit, repeated navigation with enabled controls, endpoint navigation, keyboard-opened preview retention, Escape focus restoration without reopening, and Tab navigation into and out of a mouse-opened preview. `tests/run-all.sh` discovers the new browser check automatically. `VERSION` increments from `0.4.17` to `0.4.18`.

## Verification

**failed** — Before the fix, `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python tests/browser_check_preview_dismiss.py` reproduced the selection and deselection failures. After moving the pointer away, the assertion expecting the preview to be hidden failed because the preview remained visible. A second agent independently reproduced the selection failure.

**passed** — After the fix, the same browser regression command exited with code 0. All eight cases passed, including both selection directions, viewport exit, page navigation, and keyboard focus retention. An independent agent repeated the complete regression check with the same result.

**passed** — A temporary browser route served the original `static/preview.js` from `HEAD` without changing tracked files. Both navigation-only cases passed against that baseline. Those cases verify preserved behavior rather than establish a second reproduction.

**passed** — With the same interpreter, `tests/browser_check_preview.py`, `tests/browser_check_preview_controls.py`, and `tests/browser_check_selection.py` exited with code 0 after the fix. The preview suite covers thumbnail-to-bubble movement, keyboard access, touch navigation and outside-tap dismissal, dwell, saved-progress isolation, viewport bounds, and filtering. Independent review found no implementation issues.

**passed** — `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_preview.py tests/test_organization.py` reported `10 passed`. `node --check static/preview.js` and `git diff --check` exited with code 0.
