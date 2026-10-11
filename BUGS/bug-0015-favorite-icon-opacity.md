# Bug 0015 — Favorite icon background obscures light document covers

**Status:** Open

## Observed behavior

The Favorite star sits over the upper-right corner of each cover on an opaque surface-colored circle. Many PDF and ebook covers are mostly white, making the circle more prominent than the star.

## Reproduction

Open the library with a mostly white cover and compare the Favorite control over that cover in light and dark themes.

## Expected behavior

Use a more translucent background behind the Favorite icon so the cover remains visible. Keep the star legible in its pressed and unpressed states, with a visible keyboard focus ring and a usable pointer target. The control must still expose its accessible name and `aria-pressed` state.

## Diagnosis

`static/styles.css` sets `.document-star` to `background:var(--surface)`, an opaque theme surface. The control overlaps `.document-art` in `static/app.js`.

## Proposed resolution

Use a theme-aware translucent fill and a restrained border or shadow. Check contrast against white, dark, and busy covers before choosing the final opacity.

## Verification

**not_run** — Documentation only. Compare light and dark screenshots with white, dark, and detailed cover fixtures; inspect pressed state, focus ring, and hit target.
