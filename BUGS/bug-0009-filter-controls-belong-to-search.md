# Bug 0009 — Filters are separated from the library search field

**Status:** Open

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

## Verification

**not_run** — Documentation only. Check position, overflow, focus, dismissal, state persistence, and combined search/filter results at 390 px and 1280 px.
