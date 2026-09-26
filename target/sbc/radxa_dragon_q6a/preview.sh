#!/usr/bin/env bash
# Run qcam in a terminal on the Radxa graphical desktop.
# qcam has no --script option for a fixed lens code; use web-preview.py for that.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
(( $# == 0 )) || { echo 'qcam cannot set a fixed focus code; use web-preview.py --focus CODE.' >&2; exit 2; }
if [[ -z "${IMX519_RUNTIME:-}" && -x "$task_dir/runtime/preview/bin/qcam" ]]; then
    export IMX519_RUNTIME="$task_dir/runtime/preview"
fi
exec bash "$task_dir/libcamera/run.sh" qcam \
    -c /base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a \
    -s width=1920,height=1080
