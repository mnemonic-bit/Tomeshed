# Establish Tomeshed's app shell and access model

**Source:** User-requested first version  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** None

## Decision summary

Start a standalone Tomeshed application in the repository root using VDL's broad Flask, SQLite, server-rendered template, and plain JavaScript/CSS shape. Its first running state is an empty but usable library shell. Keep VDL read-only.

## User experience

- Show `Tomeshed` and its icon in a header fixed to the top of the viewport. Reserve space so content never hides under it.
- Match the current VDL UI's visual system, responsive spacing, card and control styling, and light/dark themes. Replace video-specific labels and imagery with reading-library equivalents.
- Keep a footer fixed to the bottom with the UI version, API version, uptime, and a visible refresh action when the UI and API versions differ. The mismatch message must still appear when an old tab is left open across a deployment.
- Put a user menu in the header with `Settings` and `Log Out`. Give the menu keyboard and touch access, visible focus, Escape dismissal, and the signed-in user's name.
- Settings opens as a dedicated app view, returning to the library without a full page reload. Begin with General (light/dark/system theme) and Users for administrators. Include a settings search field so later preferences can be found in the same view.
- Before the library is populated, show an explanatory empty state. Feature 0002 adds its working import action there.
- Show a clear connection error if the API is unavailable; avoid presenting failed saves or sign-out as successes.

## Backend and state

- Provide first-run administrator setup with no preset password, sign-in, signed sessions, and POST sign-out. Require authentication for application pages and private APIs; leave only sign-in assets and a data-free health endpoint public.
- Seed normal and administrator roles. Administrators can add, suspend, reactivate, reset, and remove accounts in Settings while at least one active administrator remains. Keep document visibility decisions for Feature 0007.
- Keep account, session, role, and preference state in SQLite. Provide idempotent schema initialization so startup does not discard existing data.
- Read both served UI and API versions from this app's own `VERSION` file. Report the API version from a health/version response and compare it with the version embedded in the served HTML. Refresh is offered only when they differ.
- Keep theme preference per user. A save failure leaves the current form values visible with an error.
- Store session cookies with HTTP-only and SameSite protections; reject cross-origin state-changing browser requests. Authorize every API on the server, including later document and preview routes.

## Acceptance criteria

- A new installation starts, asks for an administrator password, then allows sign-in and sign-out; no protected page or API content is exposed after sign-out.
- With a long Settings page or narrow viewport, the header and footer stay in place and neither covers reachable content.
- The menu, Settings view, theme choice, and administrator account actions work with pointer and keyboard input.
- A page loaded with UI version A against API version B names the mismatch and offers refresh; matching versions show no warning.
- Restarting the app preserves accounts, sessions as appropriate, and preferences. Unit and browser checks cover these flows.

## Boundary

This feature creates the app shell and access boundary. Document import, cards, search results, reading, and previews have their own features.
