# Bug 0005 — Browser reader server required a repository virtual environment

**Status:** Resolved locally in `0.2.3`; awaiting a GitHub rerun.

## Observed behavior

The `Validation / Deterministic gate` passed 64 Python tests, dependency lock checks, and earlier browser checks. `tests/browser_check_preview.py` then failed when its shared `start_server()` helper tried to run `/home/runner/work/Tomeshed/Tomeshed/.venv/bin/python`. GitHub Actions installs Python through `actions/setup-python` and does not create a repository `.venv`.

## Reproduction

Run `tests/browser_check_preview.py` in a checkout without `.venv` after installing dependencies into the active Python interpreter. Before the fix, `subprocess.Popen` raised `FileNotFoundError` for `.venv/bin/python`. A local process-launch check that simulated a checkout without `.venv` exited 1 because the server executable differed from the interpreter running the check.

## Expected behavior

The reader and preview browser checks must start their Tomeshed server with the same Python interpreter that runs the checks, whether Python comes from `.venv` or `actions/setup-python`.

## Diagnosis

`tests/browser_check_reader.py` hardcoded `ROOT / '.venv/bin/python'` in `start_server()`. `tests/browser_check_preview.py` imports that helper. Other browser server helpers already use `sys.executable`.

## Resolution

Pass `sys.executable` to `subprocess.Popen` in `start_server()`.

## Verification

The local process-launch check failed before the change because the helper selected a simulated checkout's `.venv/bin/python`; it exited 0 after the change and confirmed that the helper selected `sys.executable`. `.venv/bin/python tests/browser_check_reader.py` and `.venv/bin/python tests/browser_check_preview.py` each exited 0. `./tests/run-all.sh` exited 0 at version `0.2.3`, including 64 Python tests, both architecture lock checks, all browser checks, and the isolated shipping-image smoke test. A GitHub validation rerun remains necessary to confirm the hosted gate.
