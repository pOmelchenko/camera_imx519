#!/usr/bin/env bash
# Run in a terminal on the Radxa graphical desktop. Optional argument: focus code.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
(( $# <= 1 )) || { echo 'Usage: preview.sh [focus-code]' >&2; exit 2; }
default_focus="$(cat "$task_dir/focus-position.txt")"
exec python3 "$task_dir/focus.py" "${1:-${IMX519_FOCUS:-$default_focus}}" -- \
    bash "$task_dir/libcamera/run.sh" qcam \
    -c /base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a \
    -s width=1920,height=1080
