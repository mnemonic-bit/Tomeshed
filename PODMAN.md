# Podman deployment

## Pull and replace a published image

Select an immutable `v<VERSION>` tag, full 40-character commit SHA tag, or `@sha256:<manifest-digest>` from the [Tomeshed GHCR package](https://github.com/mnemonic-bit/Tomeshed/pkgs/container/tomeshed). Pass the image reference and the version expected from `/api/health` to the replacement script. The script pulls the image before it stops the current container, retains the previous container under a timestamped name, and checks `ok: true` and the expected version. A failed health check exits nonzero and leaves the previous container available for rollback.

```bash
tomeshed_version="$(tr -d '\n' < VERSION)"
TOMESHED_PORT=5000 scripts/podman_replace.sh \
    "ghcr.io/mnemonic-bit/tomeshed:v${tomeshed_version}" "$tomeshed_version"
```

Set `TOMESHED_INGEST_HOST_DIR=/absolute/path/to/inbox` for the optional read-only inbox mount. Keep the same `TOMESHED_PORT` and inbox path on every replacement. The script uses `tomeshed-data` for SQLite and `tomeshed-documents` for preserved source files and generated artifacts. Set `TOMESHED_CONTAINER_NAME`, `TOMESHED_DATA_VOLUME`, and `TOMESHED_DOCUMENTS_VOLUME` only when testing in an isolated Podman namespace or with isolated resource names. The script never removes these volumes.

After replacement, check `curl -fsS http://127.0.0.1:${TOMESHED_PORT:-5000}/api/health` and compare its `version` with the chosen `EXPECTED_VERSION`. Run `podman ps --filter name='^tomeshed$'` to confirm the image and port. To roll back, use the commands in [Roll back a replacement](#roll-back-a-replacement) with the timestamped prior container name. A database migration or stored-file change can prevent an older image from reading the current volumes; restore a matching backup of both volumes when required.

Run these commands from the Tomeshed repository root. They use Podman directly,
so `podman compose` is not required. The container listens on all host
interfaces on port 5000 by default. Set `TOMESHED_PORT` in the shell before
running the commands to use another host port.

The `tomeshed-data` volume stores SQLite data. The `tomeshed-documents` volume
stores source documents and generated files. Keep both volumes when replacing
the container, and back them up together.

## Build and start

The same commands handle a first deployment or a replacement. The build finishes
before the current container stops. On replacement, the old container receives
a timestamped name for rollback.

```bash
tomeshed_version="$(tr -d '\n' < VERSION)"
tomeshed_host_port="${TOMESHED_PORT:-5000}"
rollback_name="tomeshed-previous-$(date -u +%Y%m%dT%H%M%SZ)"

if podman container exists "${rollback_name}"; then
    echo "Choose an unused rollback_name; ${rollback_name} already exists." >&2
    exit 1
fi

podman build \
    --tag "localhost/tomeshed:${tomeshed_version}" \
    --tag localhost/tomeshed:local \
    . || exit 1

if podman container exists tomeshed; then
    podman stop --time 10 tomeshed || exit 1
    podman rename tomeshed "${rollback_name}" || exit 1
fi

podman run --detach \
    --name tomeshed \
    --restart unless-stopped \
    --publish "0.0.0.0:${tomeshed_host_port}:5000" \
    --volume tomeshed-data:/data \
    --volume tomeshed-documents:/library \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    "localhost/tomeshed:${tomeshed_version}"
```

For an inbox, create a host directory with `install -d ingest` before starting
the container. Add `--env TOMESHED_INGEST_DIR=/ingest` and
`--volume "$(pwd)/ingest:/ingest:ro"` to `podman run` before the image name.

The inbox is disabled when `TOMESHED_INGEST_DIR` is unset. The bind mount is
read-only; Tomeshed copies accepted documents into `tomeshed-documents`.

## Verify

Check that `/api/health` reports `"ok": true` and the version in `VERSION`.
Check that the `tomeshed` container is running and publishes the expected port.
Podman's default OCI image format can omit the Dockerfile health check, so use
the HTTP endpoint for this check.

```bash
tomeshed_host_port="${TOMESHED_PORT:-5000}"
curl -fsS "http://127.0.0.1:${tomeshed_host_port}/api/health"
podman ps --filter name='^tomeshed$' \
    --format '{{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'
podman logs --tail 30 tomeshed
```

On the first visit, open `http://HOST:5000` (or the chosen host port) and set
the `admin` password.

## Roll back a replacement

If the replacement fails verification, find the saved container name with
`podman ps --all --filter name='tomeshed-previous-'`. Replace
`ROLLBACK_NAME` with that name, then run:

```bash
if podman container exists tomeshed; then
    podman stop --time 10 tomeshed
    podman rm tomeshed
fi
podman rename ROLLBACK_NAME tomeshed
podman start tomeshed
```

The rollback container uses the same named volumes. If the new version changed
the database or stored files, review that version's migration behavior before
starting the old image against those volumes.
