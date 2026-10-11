# Bug 0031 — Reader document panel needs a compact action rail and inline editors

**Status:** Resolved in `0.4.3`

## Observed behavior

The full reader's left document panel disappears entirely when minimized, leaving only a restore button over the reading area. Its minimize control shows one angle bracket, and the expanded panel repeats `Document info` and the document title already shown in the reader header. `Add to bookshelf` and `Remove document` have text-only buttons. Tags use a separate add form and suggestion buttons. Title and author changes share a `Save metadata` form, while stored filename has another rename form. The visibility select uses the browser's default colors instead of the selected theme. Original and Docling JSON exports appear as separate links.

## Reproduction

1. Open a document in the full reader. Compare the reader header with the left panel heading and title.
2. Select `Minimize document info`. Observe that the panel disappears and its actions are unavailable until it is restored.
3. Restore the panel. Inspect the text-only Add to bookshelf and Remove document buttons, the tag form, title and filename editing controls, the visibility select in light and dark themes, and the separate download links.

## Expected behavior

### Panel and actions

- Show two angle brackets on the minimize control. Minimizing leaves a narrow, full-height bar at the left of the reader, wide enough for usable action icons and a restore control. Hide metadata text and edit fields in that state; keep the chosen compact actions available. Keep the reading content beside the bar at desktop and narrow viewport widths.
- Keep an icon for Add to bookshelf and an icon for Remove document available in the compact bar. Show the same actions as icon-plus-text buttons when expanded. Give icon-only controls accessible names, visible focus, and touch-sized targets. Keep the existing removal confirmation and access rules.
- Remove the visible `Document info` heading and the separate repeated document-title heading from the panel. Keep the reader header's document title. Keep an editable Title field in the expanded panel so the title can still be changed.
- Retain the panel-state behavior requested in Bug 0030 when the reader closes and another document opens.

### Expanded panel order and editing

- Put an inline tag editor above Add to bookshelf. Show existing tags as removable chips. As the user types, show matching tags that are not already attached; let the user choose a suggestion or add the entered tag. Preserve keyboard access to suggestions, addition, removal, and dismissal. Reuse VDL's editor behavior as the interaction reference.
- Put Add to bookshelf below the tag editor. Its expanded button shows an icon followed by `Add to bookshelf`.
- Put Author with the other metadata below Add to bookshelf, rather than as a separate line above the tags. Keep author editing available without the shared `Save metadata` button.
- Provide inline Title and Stored filename editors. In display mode, show the value and an edit control. In edit mode, show an input with a check button to accept and a cross button to cancel at the end. Enter accepts and Escape cancels. Show failed saves without silently discarding the draft. Update the reader header after a successful title change. Keep Original filename as provenance metadata; it is not the stored-file rename target.
- Remove the shared `Save metadata` button once Title and Author have their own save path. Preserve the existing metadata update and file rename behavior, including validation and access checks.
- Style the visibility select and its options with the active light or dark theme's foreground, surface, and border colors, consistent with Tomeshed's other themed selects and VDL's visibility control.

### Download recommendation

Use one split download control in the expanded panel: the main `Download original` button downloads the preserved source file, and an adjacent, separately named `Choose download format` button opens a menu of every available export. Build menu entries from available formats rather than hard-coding two slots, so an original PDF or EPUB, Docling JSON, and future formats can coexist. Label each entry by format and distinguish the original from a converted export. If only one export is available, show one button without the menu segment. Make the menu usable by keyboard and touch. Keep export authorization and source availability checks unchanged.

## Diagnosis

`templates/index.html` places `readerPanelRestore` in `reader-main` and gives `readerPanelMinimize` a single `‹` glyph and a visible `Document info` heading. `static/reader.js` hides the entire panel in `setPanelMinimized()`. `static/app.js` builds the repeated title, author line, separate tag form, text-only actions, shared metadata form, filename form, visibility select, and two export links in `renderDocumentInfo()`. `static/styles.css` makes the restore control float over the reader and styles `.document-visibility select` for size but not theme colors.

The read-only VDL blueprint has an inline rename control with edit, check, and cancel modes in `VDL/static/app.js:1207-1305`; a tag editor with chips, filtered suggestions, and keyboard handling in `VDL/static/app.js:1017-1191`; and theme-colored visibility select styles in `VDL/static/styles.css:915-926`. Adapt those interactions to Tomeshed's document endpoints and panel layout.

## Resolution

The reader panel now stays beside the reading content as a 64 px action rail when minimized, including at 390 px viewport width. The rail retains accessible bookshelf and removal actions, and the expanded panel shows the same actions with icons and text. The panel uses double-angle minimize and restore controls and has no repeated heading or document title. The minimized choice continues across document opens.

The expanded panel now places removable tag chips and filtered keyboard-accessible suggestions above the bookshelf action. Title, Author, and Stored filename each have display and edit modes with accept and cancel controls. Enter accepts, Escape cancels without closing the reader, and a failed save retains the draft. Title and Author saves are serialized per document, and each request uses the latest confirmed value of the other field. Original filename remains provenance metadata. The visibility select and its options use the active theme colors. Available exports form one download control: one button for one format, or a primary original-download button and a keyboard-accessible format menu when multiple formats exist. Source authorization and removal confirmation remain in their existing endpoints and handlers.

## Verification

**passed** — Source inspection of `templates/index.html`, `static/reader.js`, `static/app.js`, and `static/styles.css` confirms the current panel structure and controls. Direct read-only inspection of the cited VDL files confirms the referenced inline editor, tag suggestion, and select styling patterns. VDL is excluded from the codebase index, so its source was read directly.

**passed** — Before the fix, `.venv/bin/python tests/browser_check_reader_panel.py` exited with code 1 on the new assertion that the redundant `Document info` heading was absent.

**passed** — A later review found that rapid Title and Author saves could overwrite one another. Before serialization, the new browser regression check exited with code 1: the API returned `Concurrent title` with the previous `Changed author` value after both saves.

**passed** — After serialization, `.venv/bin/python tests/browser_check_reader_panel.py` exited with code 0. The check covers desktop and 390 px compact layout, touch-sized rail actions, state and reading-location preservation, tag suggestion keyboard use, title failure-draft retention, rapid independent Title and Author saves, stored filename rename and cancellation, original filename provenance, theme colors, and one- and two-format download controls.

**passed** — `.venv/bin/python tests/browser_check_file_workflows.py` exited with code 0 after its panel-control expectations were updated.

**passed** — `.venv/bin/python tests/browser_check_organization.py` exited with code 0 after its panel-control expectations were updated. The existing favorite-card mutation check uses a DOM click because the fixed app header intercepted its pointer click in the current viewport; this does not test pointer reachability of that card.

**passed** — `.venv/bin/python -m pytest -q tests/test_organization.py tests/test_file_workflows.py` reported 15 passed. `node --check static/app.js && node --check static/reader.js` exited with code 0.

**failed** — The broader `.venv/bin/python tests/browser_check_reader.py` stopped at its existing line 140 close-scroll assertion before later reader checks. The test recorded `window.scrollY` as 416 before opening and 363 after closing at a 390 × 300 viewport. The Bug 0031 panel check separately passed its reading-position check during minimize and restore. The close-scroll difference remains for investigation outside this report's panel redesign.
