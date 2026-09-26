#!/usr/bin/env bash
# Capture an RGB image at a manual libcamera focus position after AE/AWB warm-up.
# Usage: snapshot.sh [focus-code]; IMX519_WIDTH/HEIGHT select output size.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
(( $# <= 1 )) || { echo 'Usage: snapshot.sh [focus-code]' >&2; exit 2; }
width="${IMX519_WIDTH:-1920}"
height="${IMX519_HEIGHT:-1080}"
[[ "$width" =~ ^[1-9][0-9]*$ && "$height" =~ ^[1-9][0-9]*$ ]] || {
    echo 'IMX519_WIDTH and IMX519_HEIGHT must be positive integers.' >&2; exit 2;
}
if [[ -z "${IMX519_RUNTIME:-}" && -x "$task_dir/runtime/preview/bin/cam" ]]; then
    export IMX519_RUNTIME="$task_dir/runtime/preview"
fi
mkdir -p "$task_dir/artifacts"
run_dir="$(mktemp -d "$task_dir/artifacts/snapshot-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
default_focus="$(cat "$task_dir/focus-position.txt")"
focus="${1:-${IMX519_FOCUS:-$default_focus}}"
python3 "$task_dir/focus_control.py" "$focus" "$run_dir/focus.yaml"
command_args=(timeout --signal=INT --kill-after=3s 30s bash "$task_dir/cam.sh"
    -c /base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a
    --stream "role=viewfinder,width=$width,height=$height,pixelformat=XRGB8888"
    --capture=90 "--script=$run_dir/focus.yaml" "--file=$run_dir/image.ppm" --metadata)
printf '%q ' "${command_args[@]}" > "$run_dir/command.txt"; printf '\n' >> "$run_dir/command.txt"
printf 'Tuning directory override: %s\n' "${IMX519_TUNING_DIR:-default}" >> "$run_dir/command.txt"
printf 'Runtime: %s\n' "${IMX519_RUNTIME:-default}" >> "$run_dir/command.txt"
printf 'Artifacts: %s\n' "$run_dir"
set +e
"${command_args[@]}" > "$run_dir/capture.log" 2>&1
status=$?
set -e
if (( status == 0 )); then
    if [[ ! -s "$run_dir/image.ppm" ]] || grep -Eiq 'failed to (write|open).*file|write error|\bERROR\b' "$run_dir/capture.log"; then
        status=1
    fi
fi
printf '%s\n' "$status" > "$run_dir/exit-status"
(( status == 0 )) || { tail -30 "$run_dir/capture.log" >&2; exit "$status"; }
printf 'Image: %s/image.ppm\n' "$run_dir"
