# GitHub repository settings

These settings require the repository owner to change GitHub state. Use the public `mnemonic-bit/Tomeshed` repository and the linked `ghcr.io/mnemonic-bit/tomeshed` package. Keep the repository description and topics about an ebook and PDF library; do not use VDL's video description. Suggested topics are `ebooks`, `pdf`, `epub`, `flask`, `podman`, and `self-hosted`.

## Actions and merge rules

1. Allow GitHub-authored Actions and the verified Docker and Anchore Actions pinned in `.github/workflows/`. Set the default `GITHUB_TOKEN` permission to read repository contents and packages. Leave permission for Actions to create or approve pull requests disabled.
2. Open a pull request containing the workflows. After its checks appear, create an **active** ruleset targeting `main`. Require a pull request, an up-to-date branch, and these exact check names from the first run: `Validation / Deterministic gate`, `CodeQL / Analyze (python)`, and `CodeQL / Analyze (javascript-typescript)`. Set zero required approvals and no bypass actor. If GitHub displays a different exact context, use the context shown by that run.
3. Test the ruleset with a pull request whose validation check fails. Confirm GitHub blocks merge. Then merge a passing pull request. Use the checked-in CodeQL advanced setup only; disable CodeQL default setup.

The `Main` workflow grants `packages: write`, `contents: write`, `attestations: write`, and `id-token: write` only to its publication job after validation. Pull request workflows have no publication credentials. Standard public repository runners are sufficient; no paid security product or runner is required.

## Security and dependency maintenance

Enable the dependency graph, Dependabot alerts, Dependabot security updates, and private vulnerability reporting. Confirm public repository secret scanning and push protection are enabled. Monthly version update pull requests cover Actions and Docker. Update `requirements.txt` and `requirements-container.txt` together in a reviewed pull request; run `tests/container/check-lock.sh` on that change. Do not enable CodeQL default setup alongside `.github/workflows/codeql.yml`.

## First package publication

The first passing `Main` run pushes `main` and a full SHA tag, then tests anonymous access before creating `v<VERSION>`, `latest`, the Git tag, and the GitHub Release. A new GHCR package may be private initially. If the anonymous check fails:

1. Open **Packages > tomeshed > Package settings**. Set visibility to **Public** and confirm the package is connected to `mnemonic-bit/Tomeshed`.
2. From a logged-out shell, pull `ghcr.io/mnemonic-bit/tomeshed:<full-commit-sha>`.
3. Rerun the same `Main` workflow. Its release policy accepts the existing SHA tag only when its digest matches the rebuilt tested image. Do not repair a partial release by overwriting its version tag; investigate the named conflict.

Retain full SHA and version tags for rollback. `main` and `latest` are movable. The workflows do not delete immutable tags. Verify the first release and public package links in `README.md` after publication.
