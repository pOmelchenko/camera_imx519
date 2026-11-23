#!/usr/bin/env bash
# Build an ARM64 runtime from a prepared source archive and recipe.
set -euo pipefail
output="${1:-/output}"
recipe="${2:-/recipe}"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT

patches=(
    imx519.patch
    autofocus-simple.patch
    color-native-size.patch
    pdaf-simple.patch
    rollback-unavailable-pdaf-link.patch
)
mkdir "$work/source"
tar -xf "$output/source.tar" -C "$work/source"
cd "$work/source"
while IFS= read -r entry; do
    [[ -z "$entry" || "$entry" == \#* ]] && continue
    patch --batch --fuzz=0 -p1 < "debian/patches/$entry"
done < debian/patches/series
for name in "${patches[@]}"; do
    patch --batch --fuzz=0 -p1 < "$recipe/$name"
done

printf '0.7.1+radxa.de1e9bc0.imx519.cdaf1\n' > .tarball-version
meson setup out --prefix=/opt/imx519-libcamera --libdir=lib --libexecdir=libexec \
    --buildtype=release --wrap-mode=nodownload \
    -Dpipelines=simple -Dipas=simple -Dsoftisp-gpu=enabled \
    -Dcam=enabled -Dqcam=disabled -Dgstreamer=disabled -Dpycamera=disabled \
    -Dv4l2=false -Ddocumentation=disabled -Dlc-compliance=disabled \
    -Dtracing=disabled -Dlibunwind=disabled -Dlibdw=disabled \
    -Drpi-awb-nn=disabled -Dtest=true
meson compile -C out -j 4
meson test -C out --suite ipa --print-errorlogs
cp out/meson-logs/testlog.txt "$output/testlog.txt"

DESTDIR="$work/install" meson install -C out --no-rebuild
runtime="$work/install/opt/imx519-libcamera"
cp "$output/source-revision.txt" .tarball-version "$recipe/run.sh" "$recipe/af-once.yaml" "$runtime/"
cp -R "$recipe/tuning" "$runtime/"
dpkg-query -W > "$runtime/build-packages.tsv"
(
    cd "$recipe"
    sha256sum "${patches[@]}" tuning/simple/imx519.yaml
) > "$runtime/recipe.sha256"
tar -czf "$output/runtime.tar.gz" -C "$runtime" .
(
    cd "$output"
    sha256sum runtime.tar.gz > runtime.sha256
)
