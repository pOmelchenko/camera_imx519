#!/usr/bin/env bash
# Five-minute color-only throughput qualification; requires a stable scene.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"
for spec in 4656x3496:9:2728 3840x2160:18:5455 2328x1748:30:9091 \
            1920x1080:60:18182 1280x720:80:24243; do
    mode="${spec%%:*}"
    rest="${spec#*:}"
    target_fps="${rest%%:*}"
    frames="${rest##*:}"
    export IMX519_WIDTH="${mode%x*}" IMX519_HEIGHT="${mode#*x}"
    export IMX519_TIMEOUT=420 IMX519_LIBCAMERA=private
    printf 'Color %s, target %s fps, %s frames\n' "$mode" "$target_fps" "$frames"
    bash stability.sh rgb "$frames"
done
