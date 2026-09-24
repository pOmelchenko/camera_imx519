#!/usr/bin/env bash
# Build a private arm64 Ubuntu 24.04 libcamera runtime using Docker.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
source_revision=de1e9bc095e23085e77533357d2582176de0a582
source_dir="$PWD/vendor/libcamera"
output_dir="$PWD/build/userspace"
if [[ ! -d "$source_dir/.git" ]]; then
    mkdir -p "$PWD/vendor"
    git clone --no-checkout https://github.com/radxa-pkg/libcamera.git "$source_dir"
fi
git -C "$source_dir" cat-file -e "$source_revision^{commit}"
mkdir -p "$output_dir"
# Archive the pinned commit: working-tree changes cannot silently enter the build.
git -C "$source_dir" archive --format=tar "$source_revision" > "$output_dir/source.tar"
printf '%s\n' "$source_revision" > "$output_dir/source-revision.txt"
docker build --platform linux/arm64 -t imx519-libcamera-builder:24.04 libcamera
docker image inspect imx519-libcamera-builder:24.04 > "$output_dir/builder-image.json"
docker run --rm --platform linux/arm64 \
    -v "$output_dir:/output" \
    -v "$PWD/libcamera:/recipe:ro" \
    imx519-libcamera-builder:24.04 bash /recipe/build-inside.sh
printf 'Runtime: %s/runtime.tar.gz\n' "$output_dir"
