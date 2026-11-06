# Bug 0046 — Library shows a redundant Books and documents heading

**Status:** Open

## Observed behavior

The library page displays `Books and documents` directly below the `Your library` label. The user requests removal of the `Books and documents` text.

## Reproduction

1. Open the library page.
2. Look at the heading above the document and bookshelf results.
3. Observe `Books and documents` below `Your library`.

## Expected behavior

Show `Your library` without the visible `Books and documents` text. Keep the `Create bookshelf` action in the library heading and retain an accessible heading for the library section.

## Diagnosis

`templates/index.html` renders `Books and documents` in the library heading's `<h2>` element, directly after the `Your library` label.

## Resolution

Pending.

## Verification

**not_run** — This report documents the requested change; no UI change or browser check has been performed.
