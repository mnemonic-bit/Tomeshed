# Bug 0004 — Release-state test used an outdated version label

**Status:** Resolved locally in `0.2.2`; awaiting a GitHub rerun.

## Observed behavior

The `Validation / Deterministic gate` Python test stage failed in `test_release_state_retry_with_mocked_github_and_registry`. The mocked image label contained `0.2.0` while `release_state.main()` read `0.2.1` from the root `VERSION` file. `release_policy.check` raised `Conflict` for the mismatched version label.

## Reproduction

Run `.venv/bin/python -m pytest -q tests/test_release_state.py::test_release_state_retry_with_mocked_github_and_registry` with root `VERSION` set to `0.2.1`. Before the fix, the command exited 1 with `existing SHA tag ... has conflicting revision or version labels`.

## Expected behavior

The retry test must provide a mocked image label matching the application version read by `release_state.main()`. A later version bump must not break the test unless release behavior changes.

## Diagnosis

The test hardcoded `0.2.0` in a fixture that calls `release_state.main()`, which reads the current root `VERSION`. The fixed `0.2.0` values in `tests/test_release_policy.py` are independent sample data and do not read `VERSION`.

## Resolution

Read the root `VERSION` file in the integration test and use its value for the mocked image label. Assert that the result reports the same version.

## Verification

The focused test failed before the change with the reported `Conflict`. After the change, `.venv/bin/python -m pytest -q tests/test_release_state.py::test_release_state_retry_with_mocked_github_and_registry` exited 0 with one test passed. `.venv/bin/python -m pytest -q tests/test_*.py` exited 0 with 64 tests passed. `./tests/run-all.sh` exited 0 with 64 Python tests, both architecture lock checks, all browser checks, and the isolated shipping-image smoke test. The smoke test confirmed health version `0.2.2`, PDF and EPUB reading, concurrent PDF requests, and persistence after container recreation. A new GitHub validation run remains necessary to confirm the hosted gate.
