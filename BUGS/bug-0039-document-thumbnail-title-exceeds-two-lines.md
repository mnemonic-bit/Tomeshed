# Bug 0039 — Document thumbnail titles exceed two lines

**Status:** Resolved in `0.4.11`

## Observed behavior

The title below a document thumbnail can wrap to three lines. Long titles make the caption taller than the desired two-line space.

## Reproduction

1. Add or find a document whose title wraps to at least three lines in the library grid.
2. View its thumbnail card at the normal library width.
3. Observe that the title occupies three or more lines below the thumbnail.

## Expected behavior

Show at most two lines of title text below each document thumbnail. Keep the current title font size and line height. If the title does not fit in two lines, truncate the visible text and show an ellipsis at the end of the second line. Titles that fit in one or two lines remain untruncated. Keep the full document title available to assistive technology and in the reader's document details.

## Diagnosis

`static/app.js` renders the full document title in `.document-copy h3`. `static/styles.css` set its font size and line height and allowed wrapping, but did not limit the number of visible lines.

## Resolution

`static/styles.css` clamps `.document-copy h3` to two lines with an ellipsis. The rule keeps the existing font size and line height. The full title remains in the heading, the card's selection button name, and the reader's document details.

## Verification

**passed** — `./.venv/bin/python tests/browser_check_document_title_clamp.py` checked short, exactly two-line, and long titles at 1280, 390, and 320 px. The browser measured one, two, and two visible lines respectively; it also confirmed the unchanged `0.97rem` font size and `1.3` line height, the full accessible heading and selection button names, and the full title in the reader header and document panel. The 390 px Chromium screenshot at `/tmp/tomeshed-bug-0039-title-390.png` shows an ellipsis at the end of the second line.
