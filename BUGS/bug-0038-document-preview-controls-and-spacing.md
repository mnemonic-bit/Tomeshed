# Bug 0038 — Document preview controls occupy too much space

**Status:** Resolved in `0.4.10`

## Observed behavior

The document preview bubble shows a `Close preview` button in a top toolbar and full-width `Previous` and `Next` buttons below the document. The location indicator sits in the top toolbar. These controls add space above and below the previewed page even though pointer users can dismiss the bubble by moving away from the originating thumbnail and bubble.

## Reproduction

1. Hover over a document thumbnail in the library until its preview bubble opens.
2. Observe the top toolbar with the location indicator and close button.
3. Observe the text `Previous` and `Next` buttons below the displayed document.
4. Move the pointer away from the thumbnail and bubble, then reopen the preview. The close button is not needed for this pointer dismissal path.

## Expected behavior

- Remove the `Close preview` button from the document preview bubble. For pointer use, keep the bubble open while the pointer moves between the originating thumbnail and bubble, including the gap between them, and close it once the pointer has left those areas. Keep an accessible dismissal path for keyboard and touch use.
- Place `Previous` and `Next` as circular buttons over the displayed document near its lower left and lower right sides. The buttons must not add a navigation row below the document or cover the location indicator.
- With a mouse or pen, hide each navigation button until the pointer enters its nearby activation region. Center that region on the button and make its diameter twice the button's visible diameter, so the hidden control can be discovered before the pointer reaches it. Keep the button visible and clickable while the pointer moves from the activation region onto it. Show keyboard-focused controls and make navigation usable on touch devices without requiring hover.
- Put the current page number, or the appropriate preview location label for non-PDF documents, in the row currently occupied by `Previous` and `Next`. Keep the indicator readable while the overlaid buttons appear.
- Remove the top toolbar's content and reduce the space above the displayed document so the top gutter matches the left and right gutters around it. Keep the bubble within its existing viewport bounds and preserve the displayed page's aspect ratio.
- Preserve disabled behavior at the first and last preview locations and keep accessible names for both navigation buttons.

## Diagnosis

The former layout put a toolbar above `#previewContent` and full-width navigation below it. Those rows increased the bubble height and made the top gutter larger than the side gutters. `static/preview.js` already kept the bubble open across the thumbnail-to-bubble gap and closed it after pointer and focus exit. Keyboard dismissal used Escape; touch dismissal depended on the removed close button.

## Resolution

`templates/index.html` now places circular navigation buttons in a stage over the displayed content and puts `#previewPosition` in a compact bottom row. `static/styles.css` gives each button a centered, invisible activation region with twice its visible diameter. Pointer type, hover, and focus reveal the controls, including on devices with both touch and mouse input. The document bubble has no top toolbar or close button. `static/preview.js` focuses a usable navigation control for keyboard and touch opening, closes on an outside touch tap, and restores thumbnail focus after that tap when the tap does not focus another control. The placement code sizes the bubble to narrow PDF pages, keeps the navigation regions inside the content stage for short excerpts, and retains the viewport limits and page aspect ratio. Feature 0004 now specifies these controls and dismissal paths.

## Verification

**passed** — `./.venv/bin/python tests/browser_check_preview_controls.py` verifies the absent toolbar and close button, equal page gutters, twice-diameter activation regions, mouse and pen hiding on a hybrid device, touch reveal, pointer navigation, first and last PDF locations, EPUB location labels, short-excerpt region containment, and 390 px placement. `./.venv/bin/python tests/browser_check_preview.py` passed twice after the final touch-focus change, including pointer bridge, keyboard focus and Escape, touch navigation and outside-tap dismissal, viewport bounds, and saved-progress isolation. `./.venv/bin/python tests/browser_check_preview_format.py` passed PDF aspect and content-height checks across PDF, EPUB, Docling, and a narrow viewport. `./.venv/bin/python tests/browser_check_preview_frame.py` passed the PDF page-transition check. `./.venv/bin/python tests/browser_check_organization.py` passed its 15 categories after replacing the removed close-button action.
