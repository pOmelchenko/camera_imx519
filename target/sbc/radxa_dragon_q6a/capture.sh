#!/usr/bin/env bash
# Usage: bash capture.sh [raw|rgb] [frame-count] [output-parent]
# Environment: IMX519_CAMERA, IMX519_WIDTH, IMX519_HEIGHT, IMX519_TIMEOUT, IMX519_LIBCAMERA.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    sed -n '2,3p' "${BASH_SOURCE[0]}"
    exit 0
fi
(( $# <= 3 )) || { echo 'Too many arguments; use --help.' >&2; exit 2; }
mode="${1:-raw}"
count="${2:-3}"
output_parent="${3:-$task_dir/artifacts}"
camera_id="${IMX519_CAMERA:-/base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a}"
camera_width="${IMX519_WIDTH:-1920}"
camera_height="${IMX519_HEIGHT:-1080}"
capture_timeout="${IMX519_TIMEOUT:-30}"
for number in "$count" "$camera_width" "$camera_height" "$capture_timeout"; do
    [[ "$number" =~ ^[1-9][0-9]*$ ]] || { echo 'Count, dimensions and timeout must be positive integers.' >&2; exit 2; }
done
case "$mode" in
    raw) stream="role=raw,width=$camera_width,height=$camera_height"; extension=bin ;;
    rgb) stream="role=viewfinder,width=$camera_width,height=$camera_height,pixelformat=XRGB8888"; extension=ppm ;;
    *) echo 'Mode must be raw or rgb; use --help.' >&2; exit 2 ;;
esac
command -v timeout >/dev/null
mkdir -p "$output_parent"
run_dir="$(mktemp -d "$output_parent/capture-$mode-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
run_dir="$(cd "$run_dir" && pwd)"
command_args=(timeout --signal=INT --kill-after=3s "${capture_timeout}s"
    bash "$task_dir/cam.sh" -c "$camera_id" --stream "$stream" "--capture=$count"
    "--file=$run_dir/frame-#.$extension" --metadata)
{
    printf 'UTC: '; date -u +%FT%TZ
    printf 'Kernel: '; uname -r
    printf 'User: '; id
    printf 'Libcamera selection: %s\n' "${IMX519_LIBCAMERA:-auto}"
    printf 'Private runtime override: %s\n' "${IMX519_RUNTIME:-default}"
    printf 'Command: '; printf '%q ' "${command_args[@]}"; printf '\n'
} > "$run_dir/command.txt"
printf 'Artifacts: %s\n' "$run_dir"
set +e
"${command_args[@]}" 2>&1 | tee "$run_dir/capture.log"
statuses=("${PIPESTATUS[@]}")
set -e
status="${statuses[0]}"
if (( status == 0 && statuses[1] != 0 )); then
    status="${statuses[1]}"
fi
printf '%s\n' "$status" > "$run_dir/exit-status"
shopt -s nullglob
frames=("$run_dir"/frame-*."$extension")
if (( status == 0 && ${#frames[@]} != count )); then
    echo "Expected $count frame files, got ${#frames[@]}." | tee -a "$run_dir/capture.log" >&2
    status=1
    printf '%s\n' "$status" > "$run_dir/exit-status"
fi
if (( status == 0 )); then
    printf 'Saved %s frames in %s\n' "${#frames[@]}" "$run_dir"
else
    printf 'Capture failed (exit %s). Log: %s/capture.log\n' "$status" "$run_dir" >&2
fi
exit "$status"
