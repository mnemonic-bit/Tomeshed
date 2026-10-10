# Security policy

## Supported versions

Report vulnerabilities affecting the current Tomeshed version in the root `VERSION` file. Older versions and untagged development snapshots are not maintained. Security fixes are handled on a best-effort basis.

GitHub Releases and published container images are planned in [Feature 0008](FEATURES/feature-0008-publish-through-github.md). Until a release exists, include the Git commit when reporting a deployment from source.

## Reporting a vulnerability

Do not disclose a vulnerability in a public issue. Use GitHub's [private vulnerability reporting](https://github.com/mnemonic-bit/Tomeshed/security/advisories/new). The repository owner must enable that GitHub setting before public launch, as recorded in [.github/REPOSITORY_SETTINGS.md](.github/REPOSITORY_SETTINGS.md).

Include the affected Tomeshed version or commit, deployment method, reproduction steps, impact, and any known mitigation. Use synthetic documents and sanitized logs. Remove account passwords, session cookies, private document contents, source URLs with tokens, filesystem paths that identify people, and database data before attaching material.

Reports are reviewed as maintainer availability permits. A response or resolution time is not guaranteed.
