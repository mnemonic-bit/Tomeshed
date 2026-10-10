#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
engine=${CONTAINER_ENGINE:-podman}
image=${TOMESHED_IMAGE:-localhost/tomeshed:smoke}
suffix="$$-$(date +%s)"
container="tomeshed-smoke-$suffix"
data="tomeshed-smoke-data-$suffix"
documents="tomeshed-smoke-documents-$suffix"
cleanup() {
    "$engine" rm -f "$container" >/dev/null 2>&1 || true
    "$engine" volume rm "$data" "$documents" >/dev/null 2>&1 || true
}
trap cleanup EXIT
if [[ "${1:-}" == --build ]]; then
    "$engine" build --pull -t "$image" "$root"
elif [[ $# -gt 0 ]]; then
    echo 'Usage: smoke.sh [--build]' >&2
    exit 2
fi
[[ $("$engine" run --rm --entrypoint id "$image" -u) == 10001 ]]
[[ $("$engine" run --rm --entrypoint id "$image" -g) == 10001 ]]
"$engine" run --rm --entrypoint python "$image" -c \
    'from pathlib import Path; root=Path("/app"); assert not any((root/name).exists() for name in ("VDL", "tests", "data", ".git", ".github")); assert not list(root.glob("*.pdf")) and not list(root.glob("*.epub"))'
"$engine" volume create "$data" >/dev/null
"$engine" volume create "$documents" >/dev/null
start() {
    "$engine" run -d --name "$container" -v "$data:/data" -v "$documents:/library" "$image" >/dev/null
    for attempt in {1..80}; do
        if "$engine" exec "$container" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health',timeout=1)" >/dev/null 2>&1; then return; fi
        sleep .5
    done
    "$engine" logs "$container" >&2
    echo 'Shipping container did not start' >&2
    exit 1
}
start
"$engine" exec -i "$container" python - phase1 "$(tr -d '\n' < "$root/VERSION")" < "$root/tests/container/smoke_client.py"
"$engine" rm -f "$container" >/dev/null
start
"$engine" exec -i "$container" python - phase2 "$(tr -d '\n' < "$root/VERSION")" < "$root/tests/container/smoke_client.py"
echo "Shipping image smoke passed: $image"
