#!/usr/bin/env bash
# IMX519_LIBCAMERA=auto (default), private, or system.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
selection="${IMX519_LIBCAMERA:-auto}"
case "$selection" in
    auto)
        if [[ -x "${IMX519_RUNTIME:-$task_dir/runtime/current}/bin/cam" ]]; then
            selection=private
        else
            selection=system
        fi ;;
    private|system) ;;
    *) echo 'IMX519_LIBCAMERA must be auto, private or system.' >&2; exit 2 ;;
esac
if [[ "$selection" == private ]]; then
    exec bash "$task_dir/libcamera/run.sh" cam "$@"
fi
exec cam "$@"
