# Feature 0008 implementation evidence

**Feature:** `FEATURES/feature-0008-publish-through-github.md`
**Baseline:** `5613dcac2c2ac6ea589b3909a32a0ec5cdc2387a`, clean working tree
**Checked tree:** Uncommitted Feature 0008 working tree on 2026-10-11
**Version:** `0.2.0`
**Status:** `blocked` pending GitHub pull-request runs, repository settings, and publication evidence.

The builder implemented the workflow, container lock, release policy, Podman replacement path, and documentation. The reviewer found one workflow defect: `setup-buildx-action` selected a builder that could not load the multi-platform image into the runner's containerd image store. The coordinator removed that step from `.github/workflows/main.yml`. The reviewer checked the correction against Docker's multi-platform GitHub Actions guidance and reported no unresolved local source finding. The corrected GitHub build path has not run on a GitHub runner.

## Local checks

| Check | Result | Evidence |
| --- | --- | --- |
| Complete validation gate | passed | Builder ran `./tests/run-all.sh` after the Bug 0002 browser-check fix; exit 0. The run included 64 `tests/test_*.py` tests, seven `tests/browser_check*.py` scripts, amd64 and arm64 hashed-lock downloads, and `tests/container/smoke.sh --build`. The reviewer independently reached 64 tests, the lock check, and three browser checks before stopping the duplicate run. |
| Shipping image smoke | passed | `tests/container/smoke.sh` used unique container and volume names. It checked UID/GID 10001, `/api/health` version `0.2.0`, PDF and EPUB imports and preserved sources, reader and preview routes with 24 concurrent PDF requests, and account, catalog, source, and reading-position persistence after recreation. The existing `tomeshed` container and `tomeshed-data` and `tomeshed-documents` volumes remained present. |
| Release policy and state tests | passed | `.venv/bin/python -m pytest -q tests/test_release_policy.py tests/test_release_state.py` exited 0 with 13 tests. Cases cover new releases, retries, partial states, conflicting SHA digests, and conflicting release artifacts. |
| Podman replacement | passed | The builder ran two isolated ad-hoc Python harnesses that invoked `scripts/podman_replace.sh ghcr.io/mnemonic-bit/tomeshed:v0.2.0 0.2.0` twice with unique container, volume, and port values. A temporary PATH wrapper replaced only `podman pull` with local image existence; all other Podman operations were real. The harnesses checked saved account, catalog, source, and position, previous-container retention, named volumes, chosen port, and the optional `/ingest` mount with `RW=false`. A real GHCR pull was not available. |
| Syntax and whitespace | passed | Builder reported `actionlint` v1.7.12, `bash -n`, and `git diff --check HEAD` exited 0. Reviewer independently ran `bash -n` and `git diff --check HEAD`, both exit 0. After the coordinator removed `setup-buildx-action`, YAML parsed and `git diff --check HEAD` exited 0; the corrected workflow has not run through `actionlint` or GitHub. |
| Preview browser-check defect | passed | `BUGS/bug-0002-preview-browser-scroll-target.md` records two reproductions, the measured page-scroll correction, a focused browser check exit 0, and the subsequent complete-gate exit 0. |

## Acceptance criteria

| ID | Result | Evidence or missing verification |
| --- | --- | --- |
| AC-01 | inconclusive | `.github/workflows/validation.yml` triggers on pull requests to `main`, grants read-only repository access, and runs `tests/run-all.sh`. No pull-request run exists for this change. |
| AC-02 | passed | The complete local gate and isolated shipping-image smoke passed as recorded above. |
| AC-03 | not_run | `.github/workflows/codeql.yml` defines Python and JavaScript analysis. `.github/REPOSITORY_SETTINGS.md` specifies an active ruleset and actual check-name verification. No workflow checks or failing-pull-request ruleset test exist yet. The public rulesets API returned `[]` on 2026-10-10. |
| AC-04 | inconclusive | `.github/workflows/main.yml` makes publication depend on a successful validation job. A controlled failed, cancelled, or skipped `main` gate has not run on GitHub. |
| AC-05 | not_run | The workflow builds and tests both platforms before pushing. No GitHub platform logs or published multi-platform manifest exist; local Podman cannot exercise the Docker Buildx runner path. |
| AC-06 | not_run | `scripts/release_policy.py` checks new and unchanged versions. Two successful `main` publication runs and their GitHub/GHCR artifacts do not exist. |
| AC-07 | passed | The 13 mocked policy/state tests passed, including partial-release and conflicting-SHA cases. The workflow runs the policy before publication. |
| AC-08 | not_run | The workflow requires anonymous SHA access and declares manifest/platform provenance and platform SPDX SBOM attestations. No public image or attestation exists to pull or verify. |
| AC-09 | passed | The isolated Podman replacement checks passed as recorded above. `scripts/podman_replace.sh` pulls before stopping the current container; the actual GHCR network pull awaits a published image. |
| AC-10 | inconclusive | Repository settings guidance, Dependabot, issue forms, `SECURITY.md`, and `README.md` use Tomeshed names and links. Live settings, package visibility, and post-publication links cannot be checked before GitHub setup. |

## External blocker and next action

This workspace has no `GITHUB_TOKEN` or `GH_TOKEN`. The new workflows are not on GitHub. The public repository currently has no ruleset and no latest Release. The repository owner must put this change on a pull request, inspect the actual validation and CodeQL check names, apply the active `main` ruleset, merge a passing pull request, make the GHCR package public if its first anonymous pull fails, and inspect both-platform images, tags, release records, SBOMs, and attestations. Rerun the failed publication workflow after package visibility is public. Do not mark Feature 0008 `completed` until the `not_run` and `inconclusive` criteria have passed.
