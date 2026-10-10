#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 2 ]]; then
    echo 'Usage: scripts/podman_replace.sh IMAGE_REFERENCE EXPECTED_VERSION' >&2
    exit 2
fi
image=$1
expected=$2
if [[ ! "$image" =~ ^ghcr\.io/[a-z0-9._/-]+(@sha256:[0-9a-f]{64}|:(v[0-9]+\.[0-9]+\.[0-9]+|[0-9a-f]{40}))$ ]]; then
    echo 'Use a GHCR digest, full commit SHA tag, or v<VERSION> tag.' >&2
    exit 2
fi
if [[ ! "$expected" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo 'EXPECTED_VERSION must be a semantic version core.' >&2
    exit 2
fi
name=${TOMESHED_CONTAINER_NAME:-tomeshed}
data=${TOMESHED_DATA_VOLUME:-tomeshed-data}
documents=${TOMESHED_DOCUMENTS_VOLUME:-tomeshed-documents}
host_port=${TOMESHED_PORT:-5000}
rollback="${name}-previous-$(date -u +%Y%m%dT%H%M%SZ)"
if podman container exists "$rollback"; then
    echo "Rollback container $rollback already exists." >&2
    exit 1
fi
podman pull "$image"
if ! podman volume exists "$data"; then podman volume create "$data" >/dev/null; fi
if ! podman volume exists "$documents"; then podman volume create "$documents" >/dev/null; fi
if podman container exists "$name"; then
    podman stop --time 10 "$name"
    podman rename "$name" "$rollback"
    echo "Previous container retained as $rollback"
fi
args=(--detach --name "$name" --restart unless-stopped
      --publish "0.0.0.0:${host_port}:5000"
      --volume "$data:/data" --volume "$documents:/library"
      --cap-drop ALL --security-opt no-new-privileges)
if [[ -n "${TOMESHED_INGEST_HOST_DIR:-}" ]]; then
    args+=(--env TOMESHED_INGEST_DIR=/ingest
           --volume "${TOMESHED_INGEST_HOST_DIR}:/ingest:ro")
fi
podman run "${args[@]}" "$image" >/dev/null
for attempt in {1..30}; do
    if health=$(curl --silent --fail "http://127.0.0.1:${host_port}/api/health") &&
        printf '%s' "$health" |
        python3 -c 'import json,sys; result=json.load(sys.stdin); sys.exit(0 if result.get("ok") is True and result.get("version")==sys.argv[1] else 1)' "$expected" 2>/dev/null; then
        echo "Health passed: ok=true version=$expected"
        exit 0
    fi
    sleep 1
done
podman logs --tail 40 "$name" >&2
echo "Health failed for $image. Previous container remains $rollback." >&2
exit 1
