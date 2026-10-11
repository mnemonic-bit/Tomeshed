# Bug 0032 — Reader controls occupy a second toolbar row and lack direct zoom entry

**Status:** Resolved in `0.4.4`

## Observed behavior

The full reader header places the document title and location label on one row, then stretches `Previous`, `Next`, zoom out, zoom in, `Mark finished`, and `Start over` across a second row. The navigation buttons use words instead of icons. Zoom has no visible percentage or direct numeric entry.

## Reproduction

1. Open a multi-page PDF in the full reader at a desktop width. Observe the text navigation buttons and separate full-width control row below the title and location.
2. Use zoom out or zoom in. Observe that the zoom percentage is not shown and cannot be entered directly.
3. Inspect the `Mark finished` and `Start over` buttons at the end of the control row.
4. Repeat with an EPUB and at a narrow viewport to inspect location wording and available header space.

## Expected behavior

- Put the reader controls in the header's right side. Keep the document title and Close control on the left, and center the current location indicator in the header. Remove the separate full-width control row. At narrow widths, keep the title, location, and controls visible or reachable without overlap or horizontal clipping.
- Show Previous and Next as distinct icon buttons with accessible names. Keep their current page or section navigation behavior. Give each a visible focus state and a touch-sized target.
- Use one segmented zoom control: a zoom-out button marked with a minus sign in the left semicircular end, a center segment with a magnifier icon and editable percentage field, and a zoom-in button marked with a plus sign in the right semicircular end. The field is a separate input, not an input nested inside a button. Show the applied percentage, update it when either outer button is used, and apply a valid entered percentage on Enter or field change. Invalid or empty input must leave the applied zoom unchanged and restore the displayed value.
- Keep the reader's supported zoom bounds unless deliberately revised; `static/reader.js` currently clamps zoom to 65–250%. Changing zoom through either buttons or direct entry keeps the current reading location in view and does not change saved progress merely because the zoom changed.
- Remove the `Mark finished` and `Start over` buttons from the reader header and its control row. Opening, navigating, and closing the reader still use the existing reading-position behavior.
- Keep the format-specific location label: PDF shows `Page N of M`; EPUB and Docling content retain their existing page or location wording when an exact `N of M` page count is unavailable.

## Diagnosis

`templates/index.html` groups all six controls in `.reader-controls` after `readerPosition`. `static/styles.css` gives that group `width:100%`, which puts the controls on their own row. `static/reader.js` handles navigation through `navigate()` and changes zoom by 15 percentage points through `zoom()`, clamped to 65–250%, without an editable percentage control. The `label()` function already produces the format-specific location text.

Feature 0003 required `Mark finished` and `Start over` in **Reading state and progress** and AC-09. `tests/browser_check_reader.py` also expected both buttons. The reader no longer exposes these actions; the authenticated completion and reset endpoints remain available.

## Resolution

The header now places Close and the title on the left, the format-specific position in the center, and icon navigation with segmented zoom on the right. At narrow widths, the controls move to a second header row without clipping. The zoom field accepts percentages from 65 through 250 on Enter or change; invalid entries restore the applied value. Zoom changes preserve the current location. The reader no longer renders or handles `Mark finished` and `Start over`. Feature 0003 and the browser checks now describe the retained backend endpoints and the removed reader actions.

## Verification

**passed** — `.venv/bin/python tests/browser_check_reader_header.py` failed before the fix on the existing completion buttons, then passed after the fix. It checks header geometry at 1000, 390, and 320 pixels; accessible icon navigation; PDF, EPUB, and Docling location labels; zoom entry, buttons, bounds, invalid input, and unchanged saved PDF progress.

**passed** — `.venv/bin/python -m pytest -q tests/test_reader.py` reported 6 passed, including the backend completion and reset behavior.

**failed (pre-existing, unrelated)** — `.venv/bin/python tests/browser_check_reader.py` stopped at line 140, where the library scroll position after closing the reader differs from the position saved before opening it. The script does not reach its later reader checks. The focused Bug 0032 browser check runs those header scenarios independently. The scroll restoration assertion remains unchanged.
