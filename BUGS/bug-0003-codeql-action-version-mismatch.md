# Bug 0003 — CodeQL action steps used different versions

**Status:** Resolved locally in `0.2.1`; awaiting a GitHub rerun.

## Observed behavior

The user reported that the CodeQL `analyze` post-action failed with `Loaded a configuration file for version '4.38.0', but running version '4.38.2'` after merging Dependabot updates for GitHub Actions. The [CodeQL run on `main`](https://github.com/mnemonic-bit/Tomeshed/actions/runs/38090845155) has a failed conclusion.

## Reproduction

On the reported revision, `.github/workflows/codeql.yml` pinned `github/codeql-action/init` to commit `b96794f015dfd88f77b49b1c93e0fa7110f94c63` (`v4.38.0`) and `github/codeql-action/analyze` to `2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2` (`v4.38.2`). A local check that extracted both pins and required equality exited 1 with `CodeQL action mismatch: init v4.38.0 vs analyze v4.38.2`.

## Expected behavior

The CodeQL `init` and `analyze` steps must run the same pinned CodeQL Action revision. The CodeQL jobs for Python and JavaScript must finish without the configuration-version error.

## Diagnosis

Dependabot updated `analyze` separately while `init` remained at `v4.38.0`. The CodeQL post-action read configuration created by a different action version. GitHub's `v4.38.2` tag resolves to commit `2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2`, which was already pinned for `analyze`.

## Resolution

Pin `init` to the same `v4.38.2` commit as `analyze`. Group `github/codeql-action/*` Dependabot version updates so future `init` and `analyze` updates arrive in one pull request.

## Verification

The local pin-equality check failed before the change with `CodeQL action mismatch: init v4.38.0 vs analyze v4.38.2`. The same check exited 0 after the change and reported that both steps use `v4.38.2` at commit `2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2`. Python parsed `.github/workflows/codeql.yml` and `.github/dependabot.yml`, and `git diff --check` exited 0. A GitHub CodeQL rerun is `not_run` for this local fix; no local check executes the GitHub post-action.
