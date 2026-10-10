# Preview a document in a page-through hover bubble

**Source:** User-requested first version  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Feature 0003

## Decision summary

When a user hovers over a ready document thumbnail, show an interactive speech bubble beside the card. It previews nearby content and lets the user page forward and back before opening the full reader. Preview navigation is temporary and never changes saved reading progress.

## Interaction and visual design

- Anchor the bubble to the hovered thumbnail with a visible pointer triangle, as in VDL's card popovers. Prefer the side with available space; flip or constrain it within the viewport on narrow screens. Keep it above the fixed footer and below the fixed header.
- Start at the user's saved reading position, or at the beginning if the document is unread. Show a page/section indicator and compact Previous and Next controls with disabled end states.
- Preview PDF pages as reduced, legible page images or canvases from the original. Preview EPUB and Docling documents as bounded content slices from the same reading order used by the full reader. Label EPUB slices as preview locations rather than exact publisher pages unless source page markers exist.
- Keep the bubble open while the pointer moves from the thumbnail into its controls. Close it when pointer/focus leaves the card and bubble, on Escape, when the reader opens, or when the card disappears after a filter change.
- Make the thumbnail's primary click open the full reader at the saved reading position. Paging within the bubble changes only its local preview cursor. An explicit `Read here` control may open the reader at the displayed preview location without first overwriting saved progress.
- Expose the same preview with keyboard focus and a labelled Preview action on touch devices. Give all controls accessible names and visible focus; avoid hover-only access to the feature.

## Delivery and performance

- Load preview content on demand for the active card, with a small cache and bounded page resolution. Do not convert the entire document or render every page on each hover.
- Serve preview content through authenticated, document-ID-based routes and the same path and visibility checks as the reader. Do not expose a public generated-image directory.
- A failed preview shows a small unavailable state while the main document card can still open in the reader. Cancel stale requests when the bubble closes or changes documents.

## Acceptance criteria

- Hovering a ready PDF or EPUB card shows the bubble beside it; Previous and Next change the displayed content without moving the card or opening the reader.
- A card near any viewport edge keeps the bubble visible without covering the fixed header/footer or trapping its controls off-screen.
- Keyboard and touch users can open, page through, and dismiss the preview.
- Previewing never changes persisted reading position or marks an unread book as read. Opening the reader still restores the last saved location.
- Anonymous users cannot fetch preview content, and repeated hover does not trigger unbounded conversion work.

## Boundary

This is a lightweight look inside a document, separate from the full reading session and its progress writes.
