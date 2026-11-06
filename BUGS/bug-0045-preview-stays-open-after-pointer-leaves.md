# Bug 0045 — Preview stays open after the pointer leaves

**Status:** Open

## Observed behavior

The user reports that the document preview sometimes remains open after the mouse pointer has moved outside both the preview bubble and its originating document thumbnail. The problem occurs most often after navigating back and forth through preview pages. The affected document formats, browsers, and frequency have not been established.

## Reproduction

1. Open a multi-page document's preview by hovering over its thumbnail.
2. Use the preview's `Previous` and `Next` controls to move back and forth through several pages.
3. Move the mouse pointer outside both the preview bubble and the originating thumbnail, then wait for the usual pointer-exit dismissal.
4. Repeat the sequence if the preview closes normally; the reported failure is intermittent.

## Expected behavior

Once the mouse pointer leaves the preview bubble and its originating thumbnail, the preview closes after its normal pointer-exit delay. Page navigation must not leave the preview open when the pointer is outside both areas.

## Diagnosis

Pending investigation. The report establishes a correlation with repeated page navigation, but does not establish the cause.

## Resolution

Pending.

## Verification

**not_run** — This report records the user's observation; no browser reproduction or fix has been performed.
