#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
python_bin=${TOMESHED_LOCK_PYTHON:-python3}
for item in 'amd64 x86_64' 'arm64 aarch64'; do
    read -r architecture machine <<< "$item"
    mkdir "$temporary/$architecture"
    timeout 300 "$python_bin" -m pip download --quiet --disable-pip-version-check \
        --dest "$temporary/$architecture" --only-binary=:all: \
        --platform "manylinux_2_28_$machine" \
        --platform "manylinux_2_27_$machine" \
        --platform "manylinux_2_26_$machine" \
        --platform "manylinux_2_17_$machine" \
        --platform "manylinux2014_$machine" \
        --implementation cp --python-version 3.12 \
        --abi cp312 --require-hashes -r "$root/requirements-container.txt"
done
echo 'Container lock resolves for linux/amd64 and linux/arm64'
