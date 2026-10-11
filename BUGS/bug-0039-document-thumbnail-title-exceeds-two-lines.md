# Bug 0039 — Document thumbnail titles exceed two lines

**Status:** Open

## Observed behavior

The title below a document thumbnail can wrap to three lines. Long titles make the caption taller than the desired two-line space.

## Reproduction

1. Add or find a document whose title wraps to at least three lines in the library grid.
2. View its thumbnail card at the normal library width.
3. Observe that the title occupies three or more lines below the thumbnail.

## Expected behavior

Show at most two lines of title text below each document thumbnail. Keep the current title font size and line height. If the title does not fit in two lines, truncate the visible text and show an ellipsis at the end of the second line. Titles that fit in one or two lines remain untruncated. Keep the full document title available to assistive technology and in the reader's document details.

## Diagnosis

`static/app.js` renders the document title in `.document-copy h3`. `static/styles.css` sets its font size and line height and allows wrapping, but does not limit the number of visible lines. No browser check was run to measure the current caption height.

## Resolution

Pending implementation.

## Verification

**not_run** — This documentation-only report does not change the caption. Verify with short, exactly two-line, and longer titles at representative library widths. Check that long titles occupy two lines with a visible ellipsis, the font size remains unchanged, and the full title remains available to assistive technology.
