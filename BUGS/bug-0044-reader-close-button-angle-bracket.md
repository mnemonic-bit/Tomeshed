# Bug 0044 — Reader Close button is a bordered text button

**Status:** Open

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

Pending implementation.

## Verification

**not_run** — This documentation-only report does not change the reader. Verify the resting, hover, and keyboard-focus appearances in light and dark themes at desktop and narrow widths. Check the accessible name, touch target, click and Escape dismissal, reader-position save, and focus return.
