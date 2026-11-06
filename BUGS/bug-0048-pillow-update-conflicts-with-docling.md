# Bug 0048 — Pillow update conflicts with pinned Docling dependencies

**Status:** Resolved locally in `0.4.17`; awaiting a GitHub rerun.

**Baseline:** Local commit `56bb112`, application version `0.4.16`. The local code, workflows, Dockerfile, and requirements match the final Dependabot merge at `30279e62faad2d10b7975ae8245194f57a40ad75`; subsequent local commits add documentation.

## Observed behavior

The [Main run 42286775448](https://github.com/mnemonic-bit/Tomeshed/actions/runs/42286775448) failed on November 6, 2026 after the final Dependabot merge at commit `30279e62faad2d10b7975ae8245194f57a40ad75`. The [Validation / Deterministic gate job](https://github.com/mnemonic-bit/Tomeshed/actions/runs/42286775448/job/128129838662) failed in `Run complete validation gate` with exit code 1. Dependency installation and Chromium installation passed. `Publish tested image` was skipped. [CodeQL passed](https://github.com/mnemonic-bit/Tomeshed/actions/runs/42286775714) for the same revision.

The [first Main run after the Pillow merge](https://github.com/mnemonic-bit/Tomeshed/actions/runs/42286386542), at `7971931`, also failed in `Run complete validation gate`. That revision precedes the Python 3.15, certifi, and pypdf merges. The GitHub API reports several intervening Main runs as cancelled, rather than failed.

Before the fix, resolving `requirements-container.txt` failed locally because Pillow `13.0.0` conflicted with the pinned Docling packages. This prevented the container dependency check and a fresh container installation from completing.

## Reproduction

Before the fix, this read-only resolver check failed from the repository root with `uv` and the existing virtual environment:

```bash
uv pip install --dry-run --python .venv/bin/python \
  --python-version 3.12 --python-platform x86_64-unknown-linux-gnu \
  --only-binary :all: --require-hashes -r requirements-container.txt
```

The command exited 1 and reported:

```text
Because docling-core==2.101.1 depends on pillow>=10.0.0,<13.0.0
And because you require pillow==13.0.0, we can conclude that your requirements are unsatisfiable.
```

The conflict also reproduces with only `docling-core==2.101.1` and `pillow==13.0.0` in a temporary requirements file. Changing only that temporary file's Pillow pin to `12.3.0` makes the minimal resolver check exit 0. No repository requirement or installed package was changed during these checks.

The complete runner command is `./tests/run-all.sh`, with `TOMESHED_TEST_PYTHON=python`, `TOMESHED_LOCK_PYTHON=python`, and `CONTAINER_ENGINE=docker` under Python 3.12. The script runs backend tests, `tests/container/check-lock.sh`, browser checks, and the container smoke test, in that order. The lock check uses pip, requires hashes, and requests binary distributions for both architectures.

## Expected behavior

The container lock contains mutually compatible package versions and verified hashes. The dependency check resolves the lock for `linux/amd64` and `linux/arm64`. The complete validation gate passes before image publication proceeds.

## Diagnosis

The reported revision of `requirements-container.txt` contained this confirmed dependency conflict:

| Package | Locked version | Published Pillow requirement |
| --- | --- | --- |
| `docling-core` | `2.101.1` | `>=10.0.0,<13.0.0` |
| `docling-slim[convert-core]` | `2.137.0` | `>=10.0.0,<13.0.0` |
| `pillow` | `13.0.0` | Conflicts with both ranges above |

The Pillow bounds were checked against installed metadata for these exact Docling versions and the published [Docling Core metadata](https://pypi.org/pypi/docling-core/2.101.1/json) and [Docling Slim metadata](https://pypi.org/pypi/docling-slim/2.137.0/json). `requirements.txt` enables the `convert-core` extra.

[Dependabot PR #8](https://github.com/mnemonic-bit/Tomeshed/pull/8), merged as `7971931`, changed the lock's Pillow pin from `12.3.0` to `13.0.0` and replaced its hashes. The pinned Docling versions stayed unchanged. Combining the individually valid package releases produced an unsatisfiable lock.

Three hypotheses were checked:

1. **Incompatible Pillow pin:** confirmed. The current complete lock fails resolution. The pre-PR-8 lock resolves for Python 3.12. A temporary copy of the current lock with only the previous Pillow version and hashes restored also resolves for Python 3.12, retaining the new certifi and pypdf versions.
2. **Python-version difference causes the reported failure:** unnecessary to reproduce the dependency conflict. The conflict occurs when explicitly targeting the runner's Python 3.12. The first affected Main run also predates the Python 3.15 merge.
3. **Another lock update is required to resolve dependencies:** the temporary Pillow-only restoration resolves the complete current lock for Python 3.12. This check does not establish application compatibility or container runtime compatibility.

**Runner evidence limitation:** Public job metadata identifies the failed step but supplies only `Process completed with exit code 1.` The job-log download endpoint returned HTTP 403, stating that repository administrator rights are required. The lock conflict is proven locally and is a likely cause of the runner failure; the exact failing subcommand in the GitHub run remains unconfirmed without its detailed log.

**Related compatibility concern:** At the reported revision, `Dockerfile` used Python `3.15.0`, while `.github/workflows/validation.yml`, the lock-generation header, and `tests/container/check-lock.sh` targeted Python 3.12. The pre-PR-8 Dockerfile already used Python `3.14.7`. Restoring Pillow compatibility alone did not establish that the lock installed on Python 3.15.

## Resolution

The user subsequently authorized the fix. Regenerated the complete lock with `uv pip compile requirements.txt --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --generate-hashes --no-annotate --upgrade-package 'pillow<13' -o requirements-container.txt`. The resolver selected Pillow `12.3.0` and its hashes. Pillow is the only changed package block; certifi `2026.10.18`, pypdf `6.21.4`, and the other locked packages remain unchanged.

Pinned `Dockerfile` to `python:3.12.14-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f`. Docker Hub's registry returned that immutable index digest for the exact tag. The container now uses the same Python minor version as validation and the lock target. The VDL blueprint also keeps its container and lock checks on Python 3.12; no VDL files were changed.

Configured `.github/dependabot.yml` to ignore Python Docker major and minor version updates while allowing patch and digest updates. Python runtime upgrades now require a coordinated review of the container, lock, and validation target. Documented this policy in `.github/REPOSITORY_SETTINGS.md`; GitHub documents the [`ignore.update-types` option](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#update-types-ignore).

Incremented `VERSION` from `0.4.16` to `0.4.17`. The existing platform dependency check exercises the actual resolver and hash-verification seam for this regression; no duplicate package-pin test was added.

Acceptance requires successful dependency resolution for both supported architectures, a passing complete gate including the shipping-image smoke test, and a passing GitHub validation job. All local gate components passed individually after the initial network timeout; confirmation of the GitHub job and publication remains pending.

## Verification

### Initial investigation

| Result | Check | Evidence or limitation |
| --- | --- | --- |
| `failed` | GitHub Main run `42286775448` | Validation step 6 exited 1; publication was skipped. |
| `passed` | `.venv/bin/python -m pytest -q tests/test_*.py` | 71 tests passed in 21.67 seconds. Local Python is `3.11.2`; installed Pillow is `12.3.0` and pypdf is `6.20.0`. This is a local baseline, not validation of the merged lock. |
| `failed` | Reported lock before the fix, `uv pip install --dry-run` targeting Python 3.12 | Binary-only resolution fails for both `x86_64-unknown-linux-gnu` and `aarch64-unknown-linux-gnu` with the Docling Core/Pillow conflict. |
| `passed` | Complete lock from `7971931^`, same Python 3.12 resolver target | 56 packages resolved; no packages installed. |
| `failed` | Minimal two-package requirements | Docling Core `2.101.1` plus Pillow `13.0.0` fails resolution. |
| `passed` | Minimal requirements with Pillow `12.3.0` | Resolver exited 0; no installed packages changed. |
| `passed` | Temporary current lock with previous Pillow pin and hashes | Binary-only Python 3.12 resolution succeeds for both architectures with 56 packages, retaining the certifi and pypdf updates. This temporary probe was removed. |
| `inconclusive` | `TOMESHED_LOCK_PYTHON=.venv/bin/python tests/container/check-lock.sh` | Pip reported an interrupted download and attempted a resume. The download was stopped with exit 143; no verdict from the complete pip check is claimed. |
| `not_run` | Complete gate, browser checks, shipping-image build, and GitHub rerun during the initial investigation | The initial request was analysis and a report. |

### Fix verification

| Result | Check | Evidence or limitation |
| --- | --- | --- |
| `passed` | Original resolver reproduction after the fix | Binary-only Python 3.12 resolution succeeds for amd64 and arm64 with the repaired checked-in lock. |
| `passed` | Clean Python `3.12.14` environment | `uv pip install --require-hashes -r requirements-container.txt` installed all 56 locked packages. `python -m pip check` reported no broken requirements. |
| `passed` | Configuration and change checks | PyYAML parsed `.github/dependabot.yml` and `.github/workflows/validation.yml`; container, workflow, and lock targets all select Python 3.12. The pinned base index includes amd64 and arm64. `git diff --check` exited 0. |
| `passed` | Backend tests with the repaired lock | The complete gate ran all `tests/test_*.py` tests in the clean Python 3.12.14 environment: 71 passed in 22.06 seconds. |
| `inconclusive` | First complete gate attempt | `TOMESHED_TEST_PYTHON=/tmp/tomeshed-bug-0048-venv/bin/python TOMESHED_LOCK_PYTHON=/tmp/tomeshed-bug-0048-venv/bin/python CONTAINER_ENGINE=podman ./tests/run-all.sh` exited 124 during the lock check's bounded network download. The remaining gate components were then run independently. Log: `/tmp/tomeshed-bug-0048-gate.log`. |
| `passed` | All 23 `tests/browser_check*.py` scripts | Used the clean Python 3.12.14 environment and Playwright 1.63.0. `browser_check_preview_frame.py` initially timed out waiting for its first preview image, then passed on an isolated retry; the remaining scripts passed. Logs: `/tmp/tomeshed-bug-0048-browser.log` and `/tmp/tomeshed-bug-0048-browser-remainder.log`. No browser or application source was changed. |
| `passed` | `CONTAINER_ENGINE=podman tests/container/smoke.sh --build` | Built the root shipping image and verified non-root operation, `/api/health` version `0.4.17`, PDF/EPUB imports and preserved sources, reading, concurrent PDF reader/preview requests, and persistence after recreation. Only isolated smoke-test volumes were used. Log: `/tmp/tomeshed-bug-0048-smoke.log`. |
| `passed` | Platform lock check with a temporary wheel cache | Downloaded 69 distinct wheels covering the 56 locked packages on both platforms and verified each wheel against a hash in the checked-in lock. `PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/tomeshed-bug-0048-wheels TOMESHED_LOCK_PYTHON=/tmp/tomeshed-bug-0048-venv/bin/python tests/container/check-lock.sh` exited 0 and reported `Container lock resolves for linux/amd64 and linux/arm64`. The script and its hash checks were unchanged. Log: `/tmp/tomeshed-bug-0048-lock.log`. |
| `not_run` | GitHub Main rerun | The local changes have not been pushed. GitHub must confirm validation and publication on the fixed revision. |
