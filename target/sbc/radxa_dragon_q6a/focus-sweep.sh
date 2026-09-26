#!/usr/bin/env bash
# Capture a settled RGB frame at each lens position, for a stationary scene.
# Usage: bash focus-sweep.sh [position ...]; defaults to 0..4095 in coarse steps.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if (( $# == 0 )); then set -- 0 512 1024 1536 2048 2560 3072 3584 4095; fi
for position in "$@"; do
    [[ "$position" =~ ^[0-9]{1,4}$ ]] && (( 10#$position <= 4095 )) || { echo 'Positions must be 0..4095.' >&2; exit 2; }
done
width="${IMX519_WIDTH:-640}"
height="${IMX519_HEIGHT:-480}"
[[ "$width" =~ ^[1-9][0-9]*$ && "$height" =~ ^[1-9][0-9]*$ ]] || {
    echo 'IMX519_WIDTH and IMX519_HEIGHT must be positive integers.' >&2; exit 2;
}
if [[ -z "${IMX519_RUNTIME:-}" && -x "$task_dir/runtime/preview/bin/cam" ]]; then
    export IMX519_RUNTIME="$task_dir/runtime/preview"
fi
mkdir -p "$task_dir/artifacts"
run_dir="$(mktemp -d "$task_dir/artifacts/focus-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
printf 'Artifacts: %s\n' "$run_dir"
printf '# Runtime: %s\n' "${IMX519_RUNTIME:-default}" > "$run_dir/commands.txt"
for position in "$@"; do
    python3 "$task_dir/focus_control.py" "$position" "$run_dir/focus-$position.yaml"
    command_args=(timeout --signal=INT --kill-after=3s 30s bash "$task_dir/cam.sh"
        -c /base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a
        --stream "role=viewfinder,width=$width,height=$height,pixelformat=XRGB8888"
        --capture=90 "--script=$run_dir/focus-$position.yaml"
        "--file=$run_dir/focus-$position.ppm" --metadata)
    printf '%q ' "${command_args[@]}" >> "$run_dir/commands.txt"; printf '\n' >> "$run_dir/commands.txt"
    "${command_args[@]}" > "$run_dir/focus-$position.log" 2>&1
    [[ -s "$run_dir/focus-$position.ppm" ]]
    if grep -Eiq 'failed to (write|open).*file|write error|\bERROR\b' "$run_dir/focus-$position.log"; then
        echo "Capture error: $run_dir/focus-$position.log" >&2; exit 1
    fi
    printf 'Captured focus=%s\n' "$position"
done
printf '0\n' > "$run_dir/exit-status"
