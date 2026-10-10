# GitHub repository settings

These settings live on GitHub and cannot be fully represented by repository files. Apply this checklist before making `mnemonic-bit/Tomeshed` public. This file does not configure GitHub Actions or publish a container image.

## Presentation

1. Set the repository description to `A local ebook and PDF library for reading and organizing documents.`
2. Add topics `ebooks`, `pdf`, `epub`, `flask`, `podman`, and `self-hosted`.
3. Leave the homepage empty unless a maintained project site exists. The root `README.md` describes installation and use.
4. If a social preview is added, use Tomeshed artwork without private documents or account data. Do not reuse VDL's video screenshot.
5. Check that GitHub recognizes the root `LICENSE` as MIT and shows the license on the repository page.

## Issue and security intake

1. Enable Issues. Check that the bug and feature forms in `.github/ISSUE_TEMPLATE/` appear in the issue chooser and that blank issues are disabled for visitors.
2. Enable private vulnerability reporting. Check that the issue chooser's private-report link opens the advisory form for `mnemonic-bit/Tomeshed`; public issues must not be the reporting path for vulnerabilities.
3. Enable the dependency graph, Dependabot alerts, and Dependabot security updates. The checked-in `.github/dependabot.yml` requests monthly Docker and GitHub Actions updates. Review alerts before changing Python dependencies; the container lock belongs to Feature 0008.
4. Check the public-repository secret-scanning and push-protection settings. Keep credentials, SQLite data, imported documents, and generated artifacts out of Git and issue attachments.

## Workflow boundary

Feature 0008 defines GitHub Actions validation, CodeQL, GHCR images, GitHub Releases, and the `main` ruleset. Add the settings and checks for those services when Feature 0008 is implemented. Do not require a check name before its workflow has run on a pull request.

Before publication, confirm that `README.md` still describes the current Tomeshed version and supported deployment commands. Repository metadata must use Tomeshed names and must not point to VDL packages or releases.
