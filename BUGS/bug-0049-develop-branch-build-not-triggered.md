# Bug 0049 — Develop branch does not trigger a build

**Status:** Resolved locally in `0.4.19`; awaiting GitHub push and pull-request verification.

**Baseline:** GitHub branch `develop` at commit `548e1c18a2f2aea7a38cd9b9b556f284db75ed3d`, application version `0.4.18`. Remote evidence checked on November 21, 2026.

## Observed behavior

The user reports that the new `develop` branch on GitHub does not build and may never have been configured to build. No failing run or error log was supplied with the report.

The [GitHub Actions runs API filtered to `develop`](https://api.github.com/repos/mnemonic-bit/Tomeshed/actions/runs?branch=develop&per_page=10) returned `total_count: 0` and an empty `workflow_runs` list. The workflow registry reports `Main`, `Validation`, and `CodeQL` as active. The workflow files on `develop` exclude `develop` from their push and pull-request branch filters.

## Reproduction

1. Open the [workflow directory at the affected revision](https://github.com/mnemonic-bit/Tomeshed/tree/548e1c18a2f2aea7a38cd9b9b556f284db75ed3d/.github/workflows).
2. Inspect the event filters in `main.yml`, `validation.yml`, and `codeql.yml`. All explicit branch filters select only `main`.
3. Query the Actions runs API for `develop`:

   ```bash
   curl --fail --silent --show-error \
     'https://api.github.com/repos/mnemonic-bit/Tomeshed/actions/runs?branch=develop&per_page=10'
   ```

4. Observe `total_count: 0`. With these workflow filters, a push to `develop` does not select the build workflow, and a pull request targeting `develop` does not select validation.

The investigation read the API and workflow sources without creating a commit, pushing a branch, or triggering a workflow. A fresh push reproduction remains pending.

## Expected behavior

Changes pushed to `develop` trigger automated validation and a container build. Pull requests targeting `develop` receive validation checks before merge.

## Diagnosis

The following configuration was confirmed through the GitHub contents API at the baseline commit:

| Workflow | Configured events | Effect on `develop` |
| --- | --- | --- |
| [Main](https://github.com/mnemonic-bit/Tomeshed/blob/548e1c18a2f2aea7a38cd9b9b556f284db75ed3d/.github/workflows/main.yml) | Pushes to `main` | No validation or image-build job starts for a push to `develop`. |
| [Validation](https://github.com/mnemonic-bit/Tomeshed/blob/548e1c18a2f2aea7a38cd9b9b556f284db75ed3d/.github/workflows/validation.yml) | Pull requests targeting `main`; reusable `workflow_call` | No direct push trigger; no pull-request trigger targeting `develop`. |
| [CodeQL](https://github.com/mnemonic-bit/Tomeshed/blob/548e1c18a2f2aea7a38cd9b9b556f284db75ed3d/.github/workflows/codeql.yml) | Pushes and pull requests for `main`; weekly schedule | Branch event filters exclude `develop`; the schedule does not provide validation for each `develop` commit. |

The missing event coverage explains why the new branch receives no automatic build. No failed `develop` build was found, so dependency, test, or container-build failures on that branch remain unverified. Bug 0048 concerns a dependency conflict in an earlier `main` build and is a separate defect.

## Resolution

Added a `push` trigger for `develop` to `.github/workflows/validation.yml` and extended its pull-request branch filter to `[main, develop]`. Both events run the existing deterministic gate through `tests/run-all.sh`, including backend tests, dependency-lock checks, browser checks, and `tests/container/smoke.sh --build`. The reusable `workflow_call` entry remains available to `Main`.

Extended the push and pull-request branch filters in `.github/workflows/codeql.yml` to cover `develop`. The weekly schedule and both language checks remain configured. `.github/workflows/main.yml` is unchanged: only a push to `main` selects publication. Development validation retains read-only repository permissions and publishes no image or release.

Added `tests/test_workflow_events.py` to verify event coverage, the validation command's path to the container build, retained `main` coverage and reusable validation, and publication scope. Documented the branch behavior in `.github/REPOSITORY_SETTINGS.md`. Incremented `VERSION` from `0.4.18` to `0.4.19`.

The regression command failed before the workflow changes with four missing-`develop` event cases and four passing cases. Three ranked hypotheses guided the checks: missing event filters, conditions suppressing the validation job, and a validation gate without a container build. Changing only the event filters makes all eight cases pass. The gate and container-build script require no changes.

Remote acceptance still requires a successful validation and container-build run associated with a pushed `develop` commit, plus validation checks on a pull request targeting `develop`. Confirm that publication remains scoped to `main` in those runs.

## Verification

### Initial investigation

| Result | Check | Evidence or limitation |
| --- | --- | --- |
| `passed` | Remote branch lookup | `GET /repos/mnemonic-bit/Tomeshed/branches/develop` returned the baseline commit. |
| `passed` | Remote workflow inspection | Contents API returned exactly the three workflow files listed above at the baseline commit; their explicit branch filters cover only `main`. |
| `passed` | Workflow registry lookup | `GET /repos/mnemonic-bit/Tomeshed/actions/workflows` reported `Main`, `Validation`, and `CodeQL` as active. |
| `passed` | Branch run-history lookup | `GET /repos/mnemonic-bit/Tomeshed/actions/runs?branch=develop&per_page=10` returned zero runs. This confirms the available history at inspection time. |
| `not_run` | Fresh push, pull request, validation gate, and container build during the initial investigation | The initial request covered documentation only. |

### Fix verification

| Result | Check | Evidence or limitation |
| --- | --- | --- |
| `failed` | Regression before the fix | `/tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_workflow_events.py` reported `4 failed, 4 passed in 0.09s`. Validation and CodeQL each lacked `develop` push and pull-request coverage. |
| `passed` | Workflow and release regressions after the fix | `/tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_workflow_events.py tests/test_release_policy.py tests/test_release_state.py` reported `21 passed in 0.19s`. |
| `passed` | Independent agent review and repeated focused checks | The reviewer found no blocking issues and independently ran the same 21 tests: `21 passed in 0.12s`. `git diff --check` exited 0. |
| `failed` | Broader backend suite | `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_*.py` reported `1 failed, 78 passed in 73.98s`. `tests/test_documents.py::test_real_docling_json_pdf_and_epub_pagination` expected PDF state `ready` but received `ready_with_warning`. |
| `failed` | Same PDF-processing test at the unchanged baseline | An agent extracted `git archive HEAD` at `548e1c18a2f2aea7a38cd9b9b556f284db75ed3d` into a temporary directory and ran `PYTHONDONTWRITEBYTECODE=1 /tmp/tomeshed-bug0045-venv/bin/python -m pytest -q tests/test_documents.py::test_real_docling_json_pdf_and_epub_pagination`. The same assertion failed: `1 failed in 0.74s`. The failure predates this workflow fix in the current environment. The temporary directory was removed. |
| `passed` | Publication scope | The event tests confirm `Main` accepts only pushes to `main`; `git diff -- .github/workflows/main.yml` is empty. Validation permissions remain `contents: read`. |
| `not_run` | GitHub push and pull-request runs | No commit was pushed and no pull request was created. Local workflow checks establish event configuration, not a successful GitHub runner execution. |
| `not_run` | Complete validation gate and container build during this fix | Only workflow event filters changed. The focused checks verify that the selected validation gate still invokes `tests/container/smoke.sh --build`; the full browser, dependency-lock, and container checks were not repeated. |
