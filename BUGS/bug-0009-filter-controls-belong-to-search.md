# Bug 0009 — Filters are separated from the library search field

**Status:** Resolved in `0.2.7`

## Observed behavior

The search field sits in the header, while a text `Filters` button and a full-width filter panel sit below the library heading. The panel does not open directly beneath the search field.

## Reproduction

Open the library at desktop and narrow widths. Activate `Filters`; observe the panel below the heading instead of a compact panel anchored to search.

## Expected behavior

Put an icon-only Filters button in the search field group. Activating it opens a compact filter popover directly beneath that group, with the existing Type, Author, Favorite, Reading state, Tags, and tag-matching controls. Keep the active-filter summary or indicator visible near search. Keep the popover within the viewport on narrow screens. The icon button needs an accessible name, expanded state, keyboard access, Escape dismissal, outside-click dismissal, and focus return.

## Diagnosis

`templates/index.html` splits `.library-search` and `.catalog-tools`; `static/styles.css` lays `.catalog-filters` out as a wide row. `static/app.js` only toggles its `hidden` state.

## Proposed resolution

Give search and its filter actions one positioned container. Render the filter panel as an anchored popover with an accessible control relationship. Keep filter values in one catalog state so reopening the popover reflects the active selection. Use Tomeshed's controls and VDL's compact, icon-led visual language as the reference.

## Resolution

`templates/index.html` groups search, an icon-only Filters button, the active-filter summary, and the existing filter controls. `static/styles.css` anchors a compact, scrollable popover beneath that group. `static/app.js` keeps the expanded state in sync, closes the popover on Escape or a click outside the panel and button, returns focus to Filters after Escape or a click on noninteractive content, and keeps focus in search when search is clicked. Existing catalog controls retain their values and continue to combine with search.

## Verification

**passed** — `.venv/bin/python tests/browser_check_filters_popover.py` checked popover placement and viewport bounds at 390 × 568 px and 1280 × 850 px, keyboard activation, Escape and outside-click dismissal, focus return, search-click dismissal with search focus preserved, visible controls, retained values, and a combined search/filter result. The check failed on the original text button before the fix and passed after the fix.

**passed** — `.venv/bin/python tests/browser_check_organization.py` checked existing tag, catalog, sort, clear-filter, favorite, and reader interactions after the popover change. Its controlled HTTP 503 responses exercised expected rollback paths.

**passed** — `.venv/bin/python tests/browser_check.py` checked header spacing and Settings navigation after the new search group increased the narrow header height. `.venv/bin/python tests/browser_check_settings_back.py` checked Settings Back at 390 px and 1280 px in light and dark themes.
