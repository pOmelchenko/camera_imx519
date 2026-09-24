#!/usr/bin/env bash
# Internal entry point, executed only inside the Docker builder.
set -euo pipefail
exec > >(tee /output/build.log) 2>&1
source_dir="$(mktemp -d /tmp/imx519-libcamera.XXXXXXXX)"
tar -xf /output/source.tar -C "$source_dir"
cd "$source_dir"
while IFS= read -r entry; do
    [[ -z "$entry" || "$entry" == \#* ]] && continue
    patch --batch --fuzz=0 -p1 < "debian/patches/$entry"
done < debian/patches/series
patch --batch --fuzz=0 -p1 < /recipe/imx519.patch
patch --batch --fuzz=0 -p1 < /recipe/autofocus-simple.patch
printf '0.7.1+radxa.de1e9bc0.imx519.af1\n' > .tarball-version
meson setup out --prefix=/opt/imx519-libcamera --libdir=lib --libexecdir=libexec \
    --buildtype=release -Dpipelines=simple -Dipas=simple -Dsoftisp-gpu=enabled \
    -Dcam=enabled -Dqcam=enabled -Dgstreamer=disabled -Dpycamera=disabled \
    -Dv4l2=false -Ddocumentation=disabled -Dlc-compliance=disabled \
    -Dtracing=disabled -Dlibunwind=disabled -Dlibdw=disabled \
    -Drpi-awb-nn=disabled -Dtest=true
meson compile -C out -j 4
meson test -C out --suite ipa --print-errorlogs
cp out/meson-logs/testlog.txt /output/testlog.txt
stage_dir="$(mktemp -d /tmp/imx519-stage.XXXXXXXX)"
DESTDIR="$stage_dir" meson install -C out --no-rebuild
runtime_dir="$stage_dir/opt/imx519-libcamera"
cp /output/source-revision.txt "$runtime_dir/"
cp /recipe/imx519.patch "$runtime_dir/"
cp /recipe/autofocus-simple.patch "$runtime_dir/"
dpkg-query -W > "$runtime_dir/build-packages.tsv"
cp /output/testlog.txt "$runtime_dir/"
cp .tarball-version "$runtime_dir/version.txt"
tar -czf /output/runtime.tar.gz -C "$runtime_dir" .
cd /output
sha256sum runtime.tar.gz > /output/runtime.sha256
cat /output/runtime.sha256
