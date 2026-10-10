# Publish Tomeshed through GitHub

**Source:** User-requested VDL deployment adaptation  
**Status:** Proposed  
**Last refined:** 2026-10-10  
**Depends on:** Features 0004 and 0006

## Outcome

Use GitHub Actions to validate every proposed change to `main`. After a tested change reaches `main`, publish Tomeshed container images to GitHub Container Registry (GHCR) and create a GitHub Release for a new `VERSION`. Give an operator a documented way to pull an immutable image and replace the running Podman container while preserving Tomeshed data.

GitHub hosts the source, checks, images, and release records. The running Tomeshed instance remains on an operator-managed host. This feature does not connect a GitHub workflow to that host or change the host automatically.

## Baseline and terms

- The current GitHub remote is `mnemonic-bit/Tomeshed`. Derive the image name from the repository context, lowercased; for this remote it is `ghcr.io/mnemonic-bit/tomeshed`.
- The root `VERSION` file is the application version. Follow `AGENTS.md` when implementation changes code. This specification change alone leaves `VERSION` unchanged.
- The root `Dockerfile`, `compose.yaml`, and `PODMAN.md` already define the application image, separate `tomeshed-data` and `tomeshed-documents` volumes, and `/api/health` verification. Preserve their data and access contracts.
- Use **validation gate** for the same deterministic checks run on pull requests and again on `main` before publication. Use **publication** for GHCR images, attestations, Git tags, and GitHub Releases. Use **release tag** for `v<VERSION>`.
- Treat `VDL/.github/workflows/{validation,main,codeql}.yml`, `VDL/.github/dependabot.yml`, and `VDL/.github/REPOSITORY_SETTINGS.md` as the current blueprint. Translate names, fixtures, dependencies, and host commands for Tomeshed; do not copy VDL's video or extension checks.

## Validation and merge rules

1. Add a pull-request workflow for changes targeting `main`. Give its jobs read-only repository permissions. Do not expose publication credentials or use `pull_request_target` to execute pull-request code.
2. Make the validation gate run every `tests/test_*.py` test, every Tomeshed `tests/browser_check*.py` browser check, and a smoke test of the image built from the root `Dockerfile`. Install the Python, Playwright Chromium, and container prerequisites on a standard GitHub-hosted runner. Use local fixtures and bounded timeouts so the gate does not depend on a live third-party document URL.
3. Exercise the shipping image as a non-root user. Check `/api/health` against `VERSION`, a PDF and an EPUB import and read path, the PDF reader and preview paths under concurrent requests, and persistence of an account, catalog record, source file, and reading position after container recreation with the same two named volumes. The smoke test must leave the local machine's existing Tomeshed containers and volumes untouched.
4. Provide one documented local command that runs the full validation gate. The GitHub workflow and local command must select the same checks. Keep generated browser screenshots, test databases, and container state out of the repository and uploaded artifacts unless a failed run needs a short-lived diagnostic artifact.
5. Run CodeQL for Python and JavaScript on pull requests and `main` pushes, using one checked-in advanced-setup workflow. Configure required check names from actual workflow runs. Do not enable CodeQL default setup alongside this workflow.
6. Document an active `main` ruleset that requires a pull request, an up-to-date branch, the validation gate, and both CodeQL checks. Set zero required approvals for the sole maintainer and no bypass actor. Apply the ruleset after the workflow checks have appeared on a pull request.

## Image build and publication

1. Add a `main` push workflow that reruns the validation gate on the exact commit being published. Make publication depend on its successful result; a failed, cancelled, or skipped check must publish nothing from that run.
2. Build one image from Tomeshed's root `Dockerfile` for `linux/amd64` and `linux/arm64`. Validate both platform variants before pushing their shared multi-platform manifest. Keep the container's non-root user, health endpoint, and separate data paths. Do not include test fixtures, runtime databases, source documents, or the gitignored `VDL/` tree in the image or build context.
3. Pin third-party Actions to reviewed full commit SHAs. Make container inputs reproducible for both platforms: pin the base image and resolve Python packages through a checked, reviewed lock or equivalent fixed-input mechanism. Do not run package updaters inside a published container.
4. Use `GITHUB_TOKEN` for GHCR and GitHub Release access. Grant `packages: write`, `contents: write`, `attestations: write`, and `id-token: write` only to the post-validation publication job. Require no separately stored registry password or attestation signing key.
5. After every successful `main` gate, publish `main` and the full Git commit SHA as image tags. Treat the SHA tag as immutable: if an existing tag points to different content, stop and report the conflict. Check that the SHA image can be pulled without registry credentials before creating a versioned release.
6. If no Git tag, GitHub Release, or GHCR image tag exists for `v<VERSION>`, publish that versioned image, update `latest`, and create the Git tag and GitHub Release from the tested commit. If all three already exist and agree on the original release commit and image version, publish only `main` and the new SHA tag. If only some exist or the three disagree, stop with a diagnostic that names each conflict; do not overwrite a version tag or guess how to repair the release.
7. Publish a multi-platform manifest for every image tag. Record the manifest digest and each platform digest. Generate an SPDX software bill of materials (SBOM) and GitHub-native provenance for both platform digests, and provenance for the manifest digest. A missing digest, SBOM, or attestation fails publication. Document commands to inspect the manifest and verify the attestations.
8. Serialize publication runs so two `main` commits cannot race to create the same release. Retain SHA and version tags for rollback; `main` and `latest` are movable references. Do not add an automatic deletion policy for immutable tags.

## Operator deployment and repository setup

- Extend `PODMAN.md` with a pull-and-replace path for an immutable `v<VERSION>`, full-SHA tag, or digest from GHCR. Pull before stopping the current container. Preserve `tomeshed-data` and `tomeshed-documents`, the optional read-only inbox mount, the chosen host port, and the prior container for rollback. After replacement, require `/api/health` to return `ok: true` and the expected `VERSION` value. Document that a database migration can limit rollback to an older image.
- Keep the local build instructions in `PODMAN.md`. Add GHCR pull, version selection, verification, and rollback instructions to `README.md`; link the package, release, and `main` workflow with badges whose values come from GitHub state rather than a second hand-maintained version string.
- Add `.github/REPOSITORY_SETTINGS.md` for settings that cannot be committed: public package visibility and repository link, Actions policy, default read-only token, the `main` ruleset, dependency alerts, private vulnerability reporting, and the first-publication steps. Require an anonymous pull of the SHA image before completing the first release. Use standard GitHub-hosted runners and controls available to a public personal GitHub Free repository; do not require a paid runner or paid security product.
- Add monthly Dependabot version updates for GitHub Actions and Docker. Keep Python dependency and lock updates coordinated in reviewed pull requests. Add CodeQL and dependency alerts without granting update jobs publication permissions.
- Adapt VDL's GitHub issue forms for Tomeshed bug reports and feature requests. Ask for the Tomeshed version, deployment method, host architecture, document format, reproduction, expected and actual behavior, and sanitized logs. Link private vulnerability reporting from the issue chooser and `SECURITY.md`; do not ask users to publish document contents or secrets in an issue.
- Keep credentials, databases, imported documents, generated artifacts, and browser reports out of GitHub source, Actions logs, and release assets. Repository description and topics may describe Tomeshed, but must not reuse VDL's video language.

## Acceptance criteria and verification

| ID | Observable result | Verification |
| --- | --- | --- |
| AC-01 | A pull request to `main` runs the complete Tomeshed validation gate with read-only permissions and publishes no package or release. | Inspect workflow permissions and a pull-request run; compare it with the documented local gate command. |
| AC-02 | The validation gate includes all current backend and browser checks plus a test of the root shipping image. Its container check proves non-root operation, health version, document flows, concurrent PDF paths, and preservation across recreation using isolated test volumes. | Run the local gate and inspect its test list and smoke output. |
| AC-03 | Python and JavaScript CodeQL checks run on a pull request. The active `main` ruleset blocks a merge with any required check failed or missing, without requiring another person's approval. | Inspect GitHub check runs and ruleset; test a failing pull request before merging a passing one. |
| AC-04 | A failed, cancelled, or skipped `main` validation gate creates no GHCR tag, attestation, Git tag, or GitHub Release for that run. | Inspect job dependencies and a controlled failed-gate run. |
| AC-05 | A passing `main` run validates `linux/amd64` and `linux/arm64` before publishing one manifest with both variants at the full-SHA and `main` tags. | Inspect platform test logs and the published manifest and digests. |
| AC-06 | On a new `VERSION`, one `v<VERSION>` image tag, matching Git tag, and GitHub Release refer to the tested commit; `latest` points to the same image. A later documentation-only merge with unchanged `VERSION` updates `main` and its SHA tag without changing that release. | Inspect two successful `main` runs and compare tags, release target, and digests. |
| AC-07 | A partial release state or an existing SHA tag with different content fails with a named conflict and leaves existing immutable artifacts unchanged. | Exercise release-policy checks with mocked GitHub and registry responses. |
| AC-08 | The first published SHA image is anonymously pullable before version publication. The manifest and both platform images have verifiable provenance, and each platform has an SPDX SBOM attestation. | Pull without credentials; inspect GHCR visibility and verify attestations by digest with GitHub CLI. |
| AC-09 | The documented Podman replacement pulls an immutable reference, preserves both production volumes and optional inbox configuration, and reports the expected `/api/health` version. The prior container remains available for rollback. | Follow `PODMAN.md` on an isolated host or isolated Podman namespace with seeded data. |
| AC-10 | `.github/REPOSITORY_SETTINGS.md`, Dependabot, issue forms, `SECURITY.md`, and README links use Tomeshed names and point to the Tomeshed repository and package. | Inspect files and live GitHub settings and links after setup. |

## Boundary and sources

Do not modify `VDL/` or deploy its image. VDL's `.github/` files and `VDL/FEATURES/feature-0014-make-repository-github-ready.md` provide the deployment model; Tomeshed's current source and tests determine its gate. GitHub Pages, video downloads, media-transcoding tests, and Firefox-extension signing are outside this feature.

The GitHub design relies on [rulesets and required checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets), [GHCR publication through Actions](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images), [public GHCR package access](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages), [container artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations), and [full-SHA Action pinning](https://docs.github.com/en/actions/reference/security/secure-use). GitHub documents [standard runners for public repositories](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) and [CodeQL advanced setup for public repositories](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/configure-code-scanning/configuring-advanced-setup-for-code-scanning).
