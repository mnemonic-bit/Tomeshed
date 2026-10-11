# Preview a document in a page-through hover bubble

**Source:** User-requested first version  
**Status:** Proposed  
**Last refined:** 2026-10-11
**Depends on:** Feature 0003

## Outcome

Let a signed-in user inspect nearby document content from a library card before opening the reader. Show an interactive preview bubble beside the card, with controls to move forward and back. Keep preview navigation separate from the saved reading position and completion state defined in Feature 0003.

## Scope and terms

- Use **preview bubble** for the speech-bubble panel anchored to a document thumbnail.
- Use **preview cursor** for the location displayed in the preview bubble. Keep the preview cursor in browser state; do not save it as a reading position.
- Show previews for Feature 0002 documents with import state `ready` or `ready_with_warning`.
- Use Feature 0003's source reading order to choose preview content. Keep preview cursors independent of per-user saved reading positions.
- Keep the full reading session, its progress writes, and its completion actions in Feature 0003.

## Opening and navigation

- Open the preview bubble after 800 ms of pointer hover over a document thumbnail.
- Open the preview bubble after 800 ms of keyboard focus on the thumbnail or a touch press-and-hold on the thumbnail. A short tap opens the reader.
- Start each document's first preview after the library page loads at its first preview location. When a preview closes, keep its last displayed location in browser state and resume there on the same library page. Keep separate cursors for separate documents. If the location count changes, resume at the nearest valid location.
- Show a location indicator below the displayed content. Overlay circular `Previous` and `Next` controls near the lower left and lower right page corners. Disable `Previous` at the first preview location and `Next` at the last preview location.
- For mouse and pen input, reveal each navigation control when the pointer enters a centered activation region with twice the visible button's diameter. Keep the control visible while the pointer moves onto it. Show focused controls and keep navigation visible on touch devices.
- On `Previous` or `Next`, change only the preview cursor and displayed content. Keep the library card in place and leave the reader closed.
- Show one preserved PDF page per preview location as a reduced page image or canvas.
- Show EPUB and DoclingDocument JSON content slices in the same source order as the reader. Bound each slice by configured text and image limits. Label EPUB slices as preview locations unless the source contains publisher page markers; do not present generated slices as exact source pages.
- Keep the preview bubble open while the pointer moves from the thumbnail to the bubble and its controls, including across the space between them.
- Close the preview bubble when both pointer and keyboard focus leave the card and bubble. Close it on Escape, on an outside touch tap, when the reader opens, or when filtering removes the originating card.
- On Escape or an outside touch tap, return keyboard focus to the thumbnail when the preview was opened by keyboard or touch and the card remains visible, unless the tap focuses another control. Restored focus does not reopen the preview.
- Open the full reader at the saved reading position when a user activates the thumbnail, even if the preview cursor has moved.
- If a `Read here` control is provided, open the reader at the preview cursor. Do not write that cursor to saved progress before the reader opens.

## Placement and accessibility

- Anchor the preview bubble and its pointer triangle to the originating thumbnail. Prefer the side with enough viewport space; use the other side when it fits better.
- If neither side fits at the intended width, reduce the bubble width and keep its controls within the viewport. Keep the entire bubble between the fixed header and footer.
- Keep the bubble's location indicator and overlaid `Previous` and `Next` controls within the viewport. Do not show a top toolbar or close button. Match the top gutter around the displayed page to its side gutters, and preserve the page's aspect ratio.
- Give the thumbnail and every bubble control an accessible name. Expose the preview's expanded state on the thumbnail. Show visible focus and preserve a keyboard path between the card and bubble.
- Let touch users open, page through, and dismiss the preview without a hover gesture.

## Content, access, and failure

- Fetch preview content only for the active document and requested preview location. Do not convert the full document or render every PDF page on each open.
- Bound the number of cached preview locations and the resolution of rendered PDF previews through explicit configuration. Reuse cached content for repeated visits to the same document and location.
- Cancel or ignore an outstanding preview response when the bubble closes or a different document becomes active. Do not display a response under another document's card.
- Serve preview content through authenticated routes addressed by document ID. Apply the reader's server-side document access and managed-storage path checks before sending preview bytes. Do not serve generated preview images from a public directory.
- If preview content cannot be loaded or rendered, show `Preview unavailable` inside the bubble. Keep the card's thumbnail action available to open the reader.
- Do not change the saved reading position or completion state when the bubble opens, pages, closes, or fails.
- If a document has no saved reading position, do not create one through preview interactions. Feature 0005 derives `unread` from the absence of reader activity; previewing does not change that state.

## Acceptance criteria and verification

| ID | Observable result | Verification |
| --- | --- | --- |
| AC-01 | Holding pointer hover over a `ready` PDF, EPUB, or DoclingDocument JSON thumbnail for 800 ms opens a bubble anchored beside that thumbnail. Each document starts at its first preview location after the library page loads, regardless of saved reading position. After preview navigation and closure, reopening that document resumes its last displayed location, while other documents retain separate cursors. If the location count changes, reopening uses a valid location. A `ready_with_warning` PDF or EPUB also opens from its preserved source. | Browser dwell and reopen checks with all three formats, both applicable import states, saved and absent positions, and document switching; backend check with a reduced location count. |
| AC-02 | Overlaid circular `Previous` and `Next` controls change the displayed PDF page or EPUB/Docling content slice without moving the card or opening the reader. The first and last locations disable the corresponding control. Mouse and pen input reveal a control inside a centered region twice its visible diameter; focused and touch controls remain visible. The location label stays in a row below the content, including EPUB location labels without publisher page markers. | Browser activation-region, focus, touch, boundary, and multi-format checks. |
| AC-03 | The pointer can move from the thumbnail into the bubble and its controls without closing it. The bubble closes when pointer and focus leave both surfaces, on Escape, on an outside touch tap, when the reader opens, and when filtering removes the card. | Browser pointer, keyboard, touch, reader-open, and filter checks. |
| AC-04 | At 390 px and 1280 px viewport widths, a card near each viewport edge keeps the bubble and its controls inside the viewport between the fixed header and footer. The pointer triangle remains aligned with the originating thumbnail. The bubble has no top toolbar or close button, the top and side gutters around a displayed page match, and the page preserves its aspect ratio. | Browser viewport, DOM layout, and page-ratio checks with edge-card fixtures. |
| AC-05 | No card shows a separate `Preview` button. Keyboard focus or touch press-and-hold on the thumbnail opens the bubble after 800 ms. A short touch tap opens the reader. Keyboard and touch users can activate `Previous` and `Next` and dismiss the bubble. The thumbnail and bubble controls have accessible names and visible focus. Escape or an outside touch tap returns focus to the thumbnail when the card remains visible and the tap does not focus another control, without reopening the bubble. | Browser keyboard, touch, and accessibility-tree checks, including short tap and hold gestures. |
| AC-06 | Moving the preview cursor does not change the current user's saved reading position or completion state. Previewing a document without a saved position does not create one. Thumbnail activation opens the reader at the saved position. If `Read here` is present, it opens at the preview cursor without a preceding progress write. | Compare position and completion records before and after preview interactions; check the reader start location and position requests. |
| AC-07 | Anonymous requests cannot retrieve preview content. A manipulated document ID cannot read a file outside managed storage. Generated preview images are not available through a public static path. | Backend authentication and path tests; direct request to a generated-image path. |
| AC-08 | Repeated opens of the same location use cached content within the configured cache bound. EPUB and Docling slices obey the configured text and image limits; PDF previews obey the configured resolution limit. A single open does not convert the full document or render every PDF page. A response from a closed or previous-card preview never appears in the current bubble. | Instrument preview fetch and render calls in browser tests with reduced limits; test a delayed response after switching cards. |
| AC-09 | A preview request or render failure shows `Preview unavailable`, while activating the card still opens the full reader when its source is readable. | Browser check with a forced preview failure and a readable source. |

## Reference and boundary

Use Feature 0002's authenticated document routes and Feature 0003's source rendering order and saved reading position. Inspect the current VDL Info popover in `VDL/static/app.js` and `VDL/static/styles.css` for viewport positioning and its pointer triangle. VDL anchors Info above or below a menu; this preview anchors beside a thumbnail. Keep all Tomeshed changes outside `VDL/`.
