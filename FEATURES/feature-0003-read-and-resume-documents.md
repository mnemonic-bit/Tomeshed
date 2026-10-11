# Read documents and resume at the last position

**Source:** User-requested first version  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Feature 0002

## Outcome

Let a signed-in user read a `ready` or `ready_with_warning` document in a continuous scrolling view. When the user returns, restore that user's saved reading position. Render PDF pages from the preserved PDF source, reflow EPUB content from the preserved EPUB source, and render DoclingDocument JSON as sanitized HTML.

## Scope and terms

- Use the stable document ID and authenticated source access from Feature 0002.
- Use **reading position** for a location saved in SQLite for one user and one document. Do not share a reading position between users.
- Use **completion state** for whether the current user explicitly marked a document finished.
- Use **source locator** for a position tied to document content rather than to viewport size. Store a source locator and a progress percentage when the format permits both.
- Use **approximate restore** when a saved source locator no longer identifies content in the current source and the reader uses a fallback position.
- Keep hover preview in Feature 0004. Require that feature's preview to leave reading positions and completion states unchanged.

## Reader behavior

- Open the reader when a user activates a `ready` or `ready_with_warning` document card. Resolve the card through its document ID.
- Show the document title, a current-position indicator, and a visible `Close` action in the reader.
- Close the reader through `Close` or Escape. Restore the library search query and scroll position, then return keyboard focus to the originating card.
- Display a PDF as its preserved pages in a continuous vertical view. Provide page navigation and zoom controls. When the user scrolls at the default zoom, show the page occupying the largest visible area as the current page.
- Display EPUB text and images in source reading order in a vertically scrollable, reflowable view. If the EPUB contains a table of contents, provide navigation through that table of contents.
- If an EPUB contains publisher page markers, use those markers for source page labels. Otherwise show a content location or percentage without claiming an exact source page.
- Render a valid DoclingDocument JSON source as HTML derived from its structured content. Remove scripts, event handlers, and unsafe URLs before rendering the HTML. Show an exact page label only when the source contains stable page information.
- If the source file is missing, show a source-missing state and a way back to the library. If rendering fails, show a rendering-error state and a way back to the library. If the source contains content the reader cannot display, show an unsupported-content state and a way back to the library.
- If the reader fails to open, leave the saved reading position and completion state unchanged.
- Make page and section navigation keyboard accessible. Keep focus visible and controls usable by touch.

## Reading position

- Save reading positions in SQLite under the current user ID and document ID. Permit a signed-in user to read or change only that user's positions.
- For PDF, store the current page number and a within-page offset between 0 and 1. For EPUB, store a locator tied to the source reading order and a progress percentage as fallback. For DoclingDocument JSON, store a structured-element locator and offset plus a progress percentage as fallback.
- After the current-position indicator stops changing for 500 ms, save the new position. Coalesce position changes during that interval into one write.
- Save the current position when the reader closes or the browser page becomes hidden. Perform progress writes without blocking reader scrolling.
- Validate the document ID, current user, and format-specific locator on the server before changing a saved position. Reject a malformed or out-of-range locator without replacing the previous position.
- On a first open, start at the beginning. On a later open, restore the current user's saved reading position, including after browser reload, sign-out and sign-in, or application restart.
- If an EPUB or Docling source locator no longer resolves, restore from the saved progress percentage and label the position as approximate. If a saved PDF page is beyond the current page count, restore to the final page and label the position as approximate.
- If the source file is missing, retain the saved reading position without writing a replacement position.
- Keep the authenticated `finish` endpoint, which records completion for the current user and document without deleting the saved position. The reader header does not expose a completion action.
- Keep the authenticated `start-over` endpoint, which clears completion for the current user and document and sets the saved position to the beginning. The reader header does not expose a reset action. Neither endpoint changes another user's progress or deletes the source file.

## Acceptance criteria and verification

| ID | Observable result | Verification |
| --- | --- | --- |
| AC-01 | Activating a `ready` or `ready_with_warning` card opens the reader for that document ID. `Close` and Escape return to the same library search query and scroll position, with focus on the originating card. | Browser navigation and focus checks with both import states. |
| AC-02 | A PDF renders from its preserved source as vertically scrollable pages. Page navigation and zoom change the view without resetting the position. At default zoom, the current-page indicator follows the page with the largest visible area. | Browser check with a multi-page PDF at default and changed zoom. |
| AC-03 | An EPUB renders source text and images in reading order and reflows when the viewport width changes. Its table of contents navigates when present. Without publisher page markers, the reader shows a location or percentage rather than an exact source page. | Browser checks with EPUB fixtures with and without a table of contents or page markers. |
| AC-04 | A DoclingDocument JSON source renders structured content as HTML. Scripts, event handlers, and unsafe URLs in a fixture do not execute or remain active. Exact page labels appear only for stable page data. | Browser rendering check and backend sanitization tests with crafted JSON fixtures. |
| AC-05 | After a user reaches PDF page 7 and closes the reader, reopening returns to page 7 within 5% of the saved page height. The same position restores after browser reload and application restart. If the source later has fewer than seven pages, the reader opens the final page and labels the restore as approximate. | Browser position check and restart test against the same SQLite database; test with a shorter replacement PDF. |
| AC-06 | After a user reaches a paragraph in an EPUB, changing viewport width or browser font size and reopening returns to that paragraph. If the saved locator no longer resolves, the reader uses the saved percentage and labels the restore as approximate. | Browser reflow check and test with an invalidated EPUB locator. |
| AC-07 | Two users can save different positions in the same document. Each user resumes at their own position after sign-out and sign-in. Anonymous and cross-user requests cannot read or change another user's position; anonymous requests cannot read document bytes. | Backend authorization tests and browser checks with two accounts. |
| AC-08 | A malformed or out-of-range progress payload is rejected and leaves the previous position unchanged. A missing source shows the source-missing state without overwriting the saved position. A rendering failure and unsupported content show their respective states without recording progress. | Backend payload tests and browser checks with missing and failing sources. |
| AC-09 | The authenticated `finish` endpoint records completion without deleting the position. The authenticated `start-over` endpoint clears completion and resumes at the beginning. Neither endpoint changes another user's progress or deletes the source. The reader header has no completion or reset buttons. | Backend state tests with two users and a browser check that the reader header has no completion or reset buttons. |
| AC-10 | Page and section controls work by keyboard and touch, focus remains visible and follows the controls' visual order, and closing the reader restores focus to its card. | Browser keyboard, touch, and focus checks. |
| AC-11 | Repeated position changes within 500 ms produce one progress write. Closing the reader or hiding the page saves the current position. A progress write does not pause reader scrolling. | Browser checks with controlled progress responses and rapid scrolling. |
| AC-12 | A DoclingDocument JSON reading position restores at the saved element and offset. If that element no longer exists, the reader uses the saved percentage and labels the restore as approximate. | Browser check with a saved Docling position and a changed structured document. |

## Reference and boundary

Use Feature 0002's preserved source files and authenticated document routes. Do not use Docling output as a replacement renderer for PDF or EPUB. Docling's EPUB conversion example documents that conversion can lose internal anchor targets; derive EPUB reading locators from the preserved source. Feature 0004 supplies the separate hover preview. Automatic book-to-book playback, video controls, and generated PDF or EPUB export are outside this feature.

Sources: [Docling supported formats](https://docling-project.github.io/docling/usage/supported_formats/), [Docling EPUB conversion and anchor limitation](https://docling-project.github.io/docling/_generated/examples/epub_conversion/), [W3C EPUB pagination guidance](https://www.w3.org/TR/epub-a11y-explain-12/).
