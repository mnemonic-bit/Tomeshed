# Read documents and resume at the last position

**Source:** User-requested first version  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Feature 0002

## Decision summary

Clicking a ready document card opens a reading view that supports continuous scrolling and restores the signed-in user's last position on a later visit. Preserve a PDF's original pages. Reflow EPUB text for the viewport while keeping a stable content locator. Use Docling for conversion, extraction, and a normalized view of Docling-format documents, not as a replacement for the original PDF or EPUB renderer.

## Reader behavior

- Open the reader from a card by its stable document ID. Provide a visible Close action, Escape behavior, a document title, and a current-position indicator. Closing returns to the same library search and scroll position.
- Display a PDF as its original pages in a continuous vertical reading view. Provide page navigation and zoom without losing the current position. At ordinary zoom, scrolling updates the current page as the page occupying the reading focus changes.
- Display an EPUB in reading order with responsive, reflowable text and images. Keep it scrollable. Offer a table of contents when the source includes one. Treat publisher page markers as authoritative only when present; otherwise display progress as a location or percentage instead of claiming an exact source page.
- A valid DoclingDocument JSON import opens as sanitized HTML derived from the structured document. It can show exact pages only if the document actually contains stable page information.
- Provide clear states for a missing original, a failed renderer, and unsupported content. Do not silently mark a failed open as read.
- Use keyboard-accessible page/section navigation, readable focus order, and touch-friendly controls. Restore focus to the originating card on close.

## Reading position

- Save progress per user and document in SQLite. For PDF, store page number plus a within-page position. For EPUB, store a stable source/content locator with a percentage fallback so font-size or viewport changes return near the same passage. For Docling HTML, store a stable element locator and offset.
- Save after meaningful movement with a debounce, when the reader closes, and when the page becomes hidden. A write must not block scrolling. The server validates the document ID, user, and locator before accepting progress.
- Opening a previously read document restores its saved position. A first open starts at the beginning. If an old locator no longer resolves after replacement or reconversion, fall back safely to the nearest surviving location and tell the user when the jump is approximate.
- Persist progress across browser reload, sign-out/sign-in, and app restart. A second user starts with independent progress. Hover previews do not write reading progress.
- Permit an explicit `Mark finished` action and a `Start over` action. Neither deletes the original or other users' progress.

## Acceptance criteria

- Scroll to PDF page 7, close, reopen, and return to page 7 near the same point, including after app restart.
- Read into an EPUB, change viewport width or font size, close, and reopen near the same text rather than at a layout-dependent page number.
- Two users can read the same document and resume at different places. An anonymous request cannot read either user's progress or document bytes.
- A malformed progress payload is rejected without changing the stored position. A missing or changed source produces an understandable recovery state.
- Hovering or paging through a preview leaves the stored reading position unchanged.

## Boundary

The reader does not require automatic book-to-book playback, video controls, or generated PDF/EPUB export. Feature 0004 supplies the separate hover preview.

Sources: [Docling supported formats](https://docling-project.github.io/docling/usage/supported_formats/), [Docling EPUB example and anchor limitation](https://docling-project.github.io/docling/_generated/examples/epub_conversion/), [W3C EPUB pagination guidance](https://www.w3.org/TR/epub-a11y-explain-12/).
