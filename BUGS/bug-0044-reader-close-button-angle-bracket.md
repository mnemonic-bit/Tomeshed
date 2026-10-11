# Bug 0044 — Reader Close button is a bordered text button

**Status:** Resolved in `0.4.16`

## Observed behavior

The full-document reader shows `Close` as a rectangular text button at the left of its header. Its shape and label take more space than the requested simple angle-bracket control.

## Reproduction

1. Open a document in the full reader.
2. Inspect the `Close` button at the left of the reader header.
3. Move the pointer over the button and observe the current rectangular hover treatment.

## Expected behavior

- Replace the visible `Close` text with a simple left-pointing angle bracket or chevron. Keep the button's accessible name as `Close reader` so the icon has a clear meaning for assistive technology.
- At rest, show the bracket without a visible enclosing shape. When the pointer enters the button, show a circular hover treatment around the bracket immediately. Give keyboard focus an equally clear circular treatment and a visible focus indicator.
- Keep the clickable target large enough for touch and keyboard use without changing the bracket's compact visual size. Keep the reader title aligned beside the control at desktop and narrow widths.
- Preserve the current close action, Escape dismissal, reader-position save, and focus return to the library card.

## Diagnosis

`templates/index.html` renders `#readerClose` with the visible text `Close`. `static/styles.css` applies the reader toolbar's rectangular button border, padding, and background to it. Tomeshed's Settings Back button already uses a left-pointing chevron based on VDL's `i-chevron` and a round hover treatment; that control provides a local visual reference for the reader button.

## Resolution

`templates/index.html` now renders a left chevron SVG in `#readerClose` and gives the button the accessible name `Close reader`. `static/styles.css` gives the control a 44 × 44 pixel target, a transparent circular resting state, and immediate circular hover and keyboard-focus treatments. The reader close handler remains in `static/reader.js`.

## Verification

**passed** — `.venv/bin/python tests/browser_check_reader_close.py` exited with code 0. It checked the accessible name, SVG, 44 × 44 pixel target, resting/hover/focus appearance, and title alignment in light and dark themes at 1000, 390, and 320 pixel widths. It also checked click and Escape dismissal, PDF page-position save and restore, library scroll restoration, and focus return to the document card.

**passed** — `.venv/bin/python tests/browser_check_reader_header.py` exited with code 0. Reader header layout and controls remained functional at desktop and narrow widths.

**passed** — `.venv/bin/python tests/browser_check_reader.py` exited with code 0. The broader reader check covered PDF, EPUB, and Docling reading and progress behavior.
