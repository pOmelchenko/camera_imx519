#!/usr/bin/env bash
# Use the private runtime, without replacing system packages. Usage: run.sh cam -l
set -euo pipefail
root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="${IMX519_RUNTIME:-$root_dir/runtime/current}"
program="${1:-cam}"
(( $# == 0 )) || shift
case "$program" in cam|qcam|ipa_verify) ;; *) echo 'Expected cam, qcam or ipa_verify.' >&2; exit 2;; esac
[[ -x "$runtime_dir/bin/$program" ]] || { echo "Runtime missing: $runtime_dir/bin/$program" >&2; exit 1; }
export LD_LIBRARY_PATH="$runtime_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LIBCAMERA_IPA_MODULE_PATH="$runtime_dir/lib/libcamera/ipa"
tuning_dir="${IMX519_TUNING_DIR:-$root_dir/libcamera/tuning}"
export LIBCAMERA_IPA_CONFIG_PATH="$tuning_dir:$runtime_dir/share/libcamera/ipa"
export LIBCAMERA_IPA_PROXY_PATH="$runtime_dir/libexec/libcamera"
exec "$runtime_dir/bin/$program" "$@"
