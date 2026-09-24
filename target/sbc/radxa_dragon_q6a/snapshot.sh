#!/usr/bin/env bash
# Capture a focused RGB image after 90 frames of AE/AWB warm-up. No display needed.
# Usage: snapshot.sh [focus-code]; default is specific to the tested scene.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
(( $# <= 1 )) || { echo 'Usage: snapshot.sh [focus-code]' >&2; exit 2; }
mkdir -p "$task_dir/artifacts"
run_dir="$(mktemp -d "$task_dir/artifacts/snapshot-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
default_focus="$(cat "$task_dir/focus-position.txt")"
command_args=(python3 "$task_dir/focus.py" "${1:-${IMX519_FOCUS:-$default_focus}}" --
    timeout --signal=INT --kill-after=3s 30s bash "$task_dir/cam.sh"
    -c /base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a
    --stream role=viewfinder,width=1920,height=1080,pixelformat=XRGB8888
    --capture=90 "--file=$run_dir/image.ppm" --metadata)
printf '%q ' "${command_args[@]}" > "$run_dir/command.txt"; printf '\n' >> "$run_dir/command.txt"
printf 'Tuning directory override: %s\n' "${IMX519_TUNING_DIR:-default}" >> "$run_dir/command.txt"
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
