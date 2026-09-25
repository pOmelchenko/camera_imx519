#!/usr/bin/env bash
# Short paired embedded/PDAF capture in one native IMX519 RAW10 sensor mode.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
mode="${1:-}"
case "$mode" in
    4656x3496|3840x2160|2328x1748|1920x1080|1280x720) ;;
    *) echo 'Usage: probe-phase-mode.sh {4656x3496|3840x2160|2328x1748|1920x1080|1280x720}' >&2; exit 2 ;;
esac
width="${mode%x*}"
height="${mode#*x}"
out="$q6a/artifacts/phase-mode-$mode-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out"
timeout --signal=INT --kill-after=3s 12s \
    cam -c 1 --stream "role=raw,width=$width,height=$height" --capture=2 \
    > "$out/raw-setup.log" 2>&1
grep -q "${width}x${height}" "$out/raw-setup.log" || {
    echo "Sensor did not select $mode" >&2
    exit 1
}
IMX519_IMAGE_WIDTH="$width" IMX519_DUAL_META_OUTPUT="$out/dual" \
    bash "$here/capture-dual-meta.sh" 16 > "$out/capture.log" 2>&1 || {
        cat "$out/capture.log"
        exit 1
    }
printf 'Mode: %s; artifacts: %s\n' "$mode" "$out"
tail -n 7 "$out/capture.log"
