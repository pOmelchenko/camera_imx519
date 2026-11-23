#!/usr/bin/env bash
# Build the pinned private libcamera runtime in an ARM64 Ubuntu container.
set -euo pipefail
recipe="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target="$(dirname -- "$recipe")"
source_revision=de1e9bc095e23085e77533357d2582176de0a582
source_dir="$target/vendor/libcamera"
if [[ ! -d "$source_dir/.git" ]]; then
    mkdir -p "$target/vendor"
    git clone --no-checkout https://github.com/radxa-pkg/libcamera.git "$source_dir"
fi
if ! git -C "$source_dir" cat-file -e "$source_revision^{commit}"; then
    git -C "$source_dir" fetch origin "$source_revision"
fi
mkdir -p "$target/build/userspace"
output="$(mktemp -d "$target/build/userspace/build.XXXXXXXX")"
git -C "$source_dir" archive --format=tar "$source_revision" > "$output/source.tar"
printf '%s\n' "$source_revision" > "$output/source-revision.txt"
docker build --platform linux/arm64 --iidfile "$output/builder-image-id.txt" "$recipe"
docker run --rm --platform linux/arm64 \
    -v "$output:/output" -v "$recipe:/recipe:ro" \
    "$(cat "$output/builder-image-id.txt")" bash /recipe/build-inside.sh
printf 'Runtime: %s/runtime.tar.gz\n' "$output"
