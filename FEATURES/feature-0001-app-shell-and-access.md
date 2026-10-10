# Establish Tomeshed's app shell and access model

**Source:** User-requested first version  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** None

## Outcome

Deliver a standalone Tomeshed application in the repository root. After an administrator sets a password and signs in, the application shows an empty library view with a fixed header and footer, account controls, Settings, and an accurate connection and version status.

## Scope and terms

- Use VDL's current Flask, SQLite, server-rendered template, and plain JavaScript/CSS application as the technical and visual reference.
- Create all Tomeshed code and configuration outside `VDL/`.
- Keep `VDL/` read-only.
- Use `normal` and `admin` as the initial role names. An **active administrator** is a user with the `admin` role who is not suspended.
- Treat a **private resource** as an application page or API response containing account, preference, or library data. Feature 0002 will add document routes to the same access boundary.
- Reserve document import, cards, search results, reading, and previews for their numbered features.
- Defer document visibility rules to Feature 0007.

## Application shell

- Render the Tomeshed name and icon in a header fixed to the top of the viewport.
- Use the current VDL interface as the reference for typography, colors, spacing, card and control styling, responsive layout, and light and dark themes.
- Use reading-library text and imagery in Tomeshed.
- Render a footer fixed to the bottom of the viewport with the served UI version, API version, and API uptime.
- Reserve enough space above and below the content so the fixed header and footer do not cover controls or text.
- Before documents have been imported, show an empty library state that explains why the library has no items. Feature 0002 adds the import action.

## Accounts and access

- On first database initialization, create the `normal` and `admin` roles and one administrator account with username `admin` and no preset password.
- Before the first library session, require the initial administrator to set a password.
- Provide username-and-password sign-in and signed sessions.
- Provide a POST sign-out action that ends the current browser session.
- After sign-out, reject requests from that session to private pages and APIs.
- Require an active signed-in user for every application page and private API.
- Keep only the sign-in flow, assets needed by that flow, and a health endpoint without account or library data public.
- Return an authentication error for an unauthenticated API request.
- Resolve the user's current account status and role on the server for each private request.
- Apply the same server-side access check to later document and preview routes.
- Store accounts, roles, the session-signing secret, and preferences in SQLite.
- Make schema initialization idempotent and preserve existing records during migration.
- Preserve the session-signing secret across restarts so an otherwise valid session remains valid.
- Set signed session cookies to HTTP-only and `SameSite=Lax`.
- Reject browser requests that change state when their Origin or Fetch Metadata identifies a different site.
- Show the signed-in user's name in a header menu with `Settings` and `Log Out`.
- Support pointer and touch activation, keyboard navigation, visible focus, and Escape dismissal for the header menu.
- In Settings, let administrators add, suspend, reactivate, reset the password of, and remove accounts.
- Reject any account change that would leave no active administrator, including suspending or removing the last one.

## Settings

- Open Settings as a dedicated view within the current page.
- Provide a return action that restores the library view without reloading the page.
- Show a General section with a per-user theme preference: light, dark, or system.
- Apply the system theme according to the browser's color-scheme setting.
- Show a Users section to administrators.
- Hide the Users section from normal users.
- Reject account-management API requests from normal users.
- Provide a Settings search field that filters settings by their visible labels and supporting text.
- If no setting matches the search, show an empty-results message.
- If a theme save fails, keep the selected form value visible.
- If a theme save fails, display the error in Settings.

## Version and health state

- Read the served UI version and API version from Tomeshed's own `VERSION` file.
- Embed the served UI version in the HTML.
- Return the API version and uptime from the public health endpoint.
- Check health when the page loads, at intervals of no more than 30 seconds while the page is visible, and when a hidden page becomes visible again.
- Compare the embedded UI version with the latest reported API version.
- If both versions are available and differ, show both values and explain the mismatch.
- If both versions are available and differ, offer a page refresh action.
- If both versions are available and match, hide the mismatch message and refresh action.
- If the health request fails, show a connection error and mark the API version and uptime as unavailable.
- If a save or sign-out fails, do not report the action as successful.
- If the API version is unavailable, do not describe it as a confirmed mismatch.

## Acceptance criteria and verification

| ID | Observable result | Verification |
| --- | --- | --- |
| AC-01 | A fresh database presents administrator password setup without a preset password. A valid setup permits sign-in; an invalid or repeated setup attempt does not replace the password. | Backend setup tests and a browser first-run check. |
| AC-02 | A signed-out browser cannot open a private page or read a private API response. The public health endpoint returns version and uptime without account or library data. | Backend route tests before sign-in and after POST sign-out. |
| AC-03 | Normal users cannot see Users in Settings or call account-management APIs. Administrators can add, suspend, reactivate, reset passwords, and remove accounts by pointer and keyboard. An operation that would remove the last active administrator fails. | Backend authorization tests and browser account-management checks with pointer and keyboard. |
| AC-04 | Accounts, roles, theme preferences, and the session-signing secret survive an application restart. A valid signed-in session remains usable after restart; a suspended or removed account does not. | Restart the app against the same SQLite database and exercise the affected accounts and session. |
| AC-05 | At 390 px and 1280 px viewport widths, the fixed header and footer remain visible. On a long Settings page, every control and the final content row can be reached without being covered by either bar. | Browser viewport and scrolling checks. |
| AC-06 | The menu opens with pointer, touch, Enter, and Space; its actions are keyboard reachable; focus remains visible; Escape closes it. Settings opens and returns to the library without a document reload. | Browser interaction checks. |
| AC-07 | Light, dark, and system themes render on the library and Settings views. The selected theme survives sign-out and sign-in for the same user. A failed save keeps the selected form value and shows an error. | Browser theme and failed-request checks plus a preference persistence test. |
| AC-08 | Settings search finds a setting by label or supporting text and reports when no setting matches. | Browser search checks. |
| AC-09 | The footer shows the embedded UI version, the health response's API version, and uptime. A visible page left open while the API version changes shows both versions and a refresh action within 30 seconds; a hidden page does so when it becomes visible again. Matching versions hide the warning. | Browser check with controlled health responses and page visibility changes. |
| AC-10 | When the API is unavailable, the page shows a connection error and unavailable API version and uptime. Failed saves and sign-out attempts are not reported as successes. | Browser checks with failed health and mutation requests. |
| AC-11 | Cross-site browser mutation requests are rejected while same-site requests work. Session cookies are HTTP-only and use `SameSite=Lax`. | Backend request tests and response-header checks. |
| AC-12 | At 390 px and 1280 px viewport widths, Tomeshed's header, footer, Settings controls, and light and dark themes follow the corresponding VDL layout and styling while using reading-library labels and imagery. | Review browser screenshots of Tomeshed beside the current VDL interface at both widths. |
| AC-13 | Before any document is imported, the library view explains why it has no items and contains no import control. | Browser check against a fresh database. |

## Reference and boundary

Inspect the current VDL implementation when implementing a comparable flow: `VDL/vdl.py` for authentication, SQLite, health, and version handling; `VDL/templates/index.html`, `VDL/static/app.js`, and `VDL/static/styles.css` for the page shell and Settings; and `VDL/tests/` for verification patterns. If a VDL feature document differs from current source, use the source as the technical reference. Do not add VDL's video download, playback, transcoding, or browser-extension behavior to Tomeshed.
