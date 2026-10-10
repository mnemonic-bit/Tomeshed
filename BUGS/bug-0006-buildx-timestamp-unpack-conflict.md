# Bug 0006 — Buildx timestamp rewrite conflicted with image unpack

**Status:** Resolved locally in `0.2.4`; awaiting a GitHub rerun.

## Observed behavior

The `Main / Publish tested image` job built both platform manifests, then failed during export with `exporter option "rewrite-timestamp" conflicts with "unpack"`. No platform smoke test or publication step ran.

## Reproduction

Run the `Build both platforms locally` step in `.github/workflows/main.yml` on a Docker runner with the containerd image store. The `docker` Buildx driver maps `--output type=docker,rewrite-timestamp=true` to an image export that unpacks the result into the local store. BuildKit rejects timestamp rewriting and unpacking in the same export.

## Expected behavior

BuildKit must normalize image file timestamps, and the runner must load the same multi-platform image for both smoke tests before publishing it.

## Diagnosis

The workflow requested `rewrite-timestamp=true` while its exporter also unpacked the image. BuildKit reports those exporter options as conflicting. The [BuildKit reproducibility guide](https://github.com/moby/buildkit/blob/master/docs/build-repro.md) documents timestamp rewriting, and [Docker's exporter guide](https://docs.docker.com/build/exporters/oci-docker/) documents OCI archive output with `rewrite-timestamp`.

## Resolution

Create a Buildx `docker-container` builder and export the multi-platform image to an OCI archive with `rewrite-timestamp=true`. Load the archive into Docker after export and check that the full-SHA tag is present before running either platform smoke test. Keep the Git commit timestamp as `SOURCE_DATE_EPOCH`.

## Verification

The reported GitHub failure is the pre-fix reproduction. `python3` with PyYAML parsed `.github/workflows/main.yml`, `bash -n` accepted the extracted build step, and `git diff --check` exited 0. `./tests/run-all.sh` exited 0 at version `0.2.4`: 64 Python tests, both platform lock checks, all browser checks, and the isolated shipping-image smoke test passed. This workspace has Podman rather than Docker Buildx, so the OCI export and load must be confirmed by a GitHub runner. The feature remains blocked until the runner validates both platforms and publishes the matching manifest.
