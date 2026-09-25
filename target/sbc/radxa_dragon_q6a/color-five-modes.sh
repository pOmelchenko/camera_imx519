#!/usr/bin/env bash
# Five-minute color-only throughput qualification; requires a stable scene.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"
mkdir -p artifacts
run_root="$(mktemp -d "$here/artifacts/color-five-modes-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
for spec in 4656x3496:9:3000 3840x2160:18:6000 2328x1748:30:10000 \
            1920x1080:60:20000 1280x720:80:26667; do
    mode="${spec%%:*}"
    rest="${spec#*:}"
    target_fps="${rest%%:*}"
    frames="${rest##*:}"
    export IMX519_WIDTH="${mode%x*}" IMX519_HEIGHT="${mode#*x}"
    export IMX519_TIMEOUT=420 IMX519_LIBCAMERA=private
    printf 'Color %s, target %s fps, %s frames\n' "$mode" "$target_fps" "$frames"
    IMX519_RESULT_DIR_FILE="$run_root/$mode.path" bash stability.sh rgb "$frames"
    python3 - "$run_root/$mode.path" "$mode" "$target_fps" <<'PY'
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1]).read_text().strip()
mode = sys.argv[2]
target_fps = int(sys.argv[3])
summary = json.loads((Path(run_dir) / 'summary.json').read_text())
if (summary['sensor_input'] != mode or summary['output'] != mode or
        summary['seconds_between_first_last'] < 300 or
        summary['mean_fps'] < target_fps * 0.98):
    raise SystemExit(f'{mode}: duration, FPS or mode selection failed: {summary}')
print(f'{mode}: five-minute color throughput passed')
PY
done
printf 'Five-mode summary paths: %s\n' "$run_root"
