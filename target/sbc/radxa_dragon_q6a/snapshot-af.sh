#!/usr/bin/env bash
# Capture one PPM after in-stream AF (PDAF with CDAF fallback when available).
# Usage: bash snapshot-af.sh [auto|continuous]
# Set IMX519_WIDTH and IMX519_HEIGHT for a different output size.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-auto}"
width="${IMX519_WIDTH:-1920}"
height="${IMX519_HEIGHT:-1080}"
(( $# <= 1 )) || { echo 'Usage: snapshot-af.sh [auto|continuous]' >&2; exit 2; }
[[ "$width" =~ ^[1-9][0-9]*$ && "$height" =~ ^[1-9][0-9]*$ ]] || {
    echo 'IMX519_WIDTH and IMX519_HEIGHT must be positive integers.' >&2; exit 2;
}
case "$mode" in
    auto) script="$task_dir/libcamera/af-once.yaml" ;;
    continuous) script="$task_dir/libcamera/af-continuous.yaml" ;;
    *) echo 'Expected auto or continuous.' >&2; exit 2 ;;
esac
mkdir -p "$task_dir/artifacts"
run_dir="$(mktemp -d "$task_dir/artifacts/snapshot-af-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
command_args=(timeout --signal=INT --kill-after=3s 60s bash "$task_dir/cam.sh"
    -c /base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a
    --stream "role=viewfinder,width=$width,height=$height,pixelformat=XRGB8888"
    --capture=360 "--script=$script" "--file=$run_dir/image.ppm" --metadata)
printf '%q ' "${command_args[@]}" > "$run_dir/command.txt"
printf '\n' >> "$run_dir/command.txt"
printf 'Artifacts: %s\n' "$run_dir"
set +e
IMX519_LIBCAMERA=private "${command_args[@]}" > "$run_dir/capture.log" 2>&1
status=$?
set -e
if (( status == 0 )); then
    [[ -s "$run_dir/image.ppm" ]] || status=1
    state="$(grep 'AfState = ' "$run_dir/capture.log" | tail -1 | awk '{print $3}' || true)"
    [[ "$state" == 2 ]] || status=1
    if grep -Eiq 'failed to (write|open).*file|write error|\bERROR\b' "$run_dir/capture.log"; then
        status=1
    fi
fi
printf '%s\n' "$status" > "$run_dir/exit-status"
(( status == 0 )) || { tail -30 "$run_dir/capture.log" >&2; exit 1; }
printf 'Image: %s/image.ppm\n' "$run_dir"
