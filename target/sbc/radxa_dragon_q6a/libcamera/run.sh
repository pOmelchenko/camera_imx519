#!/usr/bin/env bash
# Launch cam from the unpacked private runtime.
set -euo pipefail
runtime="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export LD_LIBRARY_PATH="$runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LIBCAMERA_IPA_MODULE_PATH="$runtime/lib/libcamera/ipa"
export LIBCAMERA_IPA_CONFIG_PATH="$runtime/tuning:$runtime/share/libcamera/ipa"
export LIBCAMERA_IPA_PROXY_PATH="$runtime/libexec/libcamera"
exec "$runtime/bin/cam" "$@"
