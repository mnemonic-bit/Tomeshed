# Bug 0038 — Document preview controls occupy too much space

**Status:** Open

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

The current layout is defined by `templates/index.html`'s `.preview-toolbar`, `#previewContent`, and `.preview-controls`. `static/styles.css` displays the toolbar and controls as separate flex rows, and `static/preview.js` binds the close and navigation buttons. The pointer exit path already calls `close()` when the pointer and focus are outside the active card and bubble. Feature 0004 currently specifies a close button and requires touch dismissal; its preview requirements will need to reflect the approved replacement behavior when this report is resolved.

## Resolution

Pending implementation.

## Verification

**not_run** — This documentation-only report does not change the preview UI. Verify the layout and activation region with a browser check that moves the pointer from outside to just inside the two-diameter region, activates each overlaid button, and moves away again. Also check keyboard focus, touch navigation and dismissal, first and last locations, PDF and non-PDF location labels, and narrow viewports.
