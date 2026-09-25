#!/usr/bin/env bash
# Capture embedded DT0x12 and phase DT0x36 concurrently on Q6A.
# Requires the experimental CAMSS module with shared-subdevice stream refs.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
count="${1:-24}"
image_width="${IMX519_IMAGE_WIDTH:-4656}"
[[ "$count" =~ ^[0-9]+$ ]] && (( count >= 2 && count <= 100 )) || {
    echo 'Usage: capture-dual-meta.sh [COUNT=2..100]' >&2
    exit 2
}
[[ "$image_width" =~ ^[0-9]+$ ]] && (( image_width >= 1280 && image_width <= 4656 )) || {
    echo 'IMX519_IMAGE_WIDTH must name the selected sensor mode' >&2
    exit 2
}
bash "$here/prepare-phase.sh"
out="${IMX519_DUAL_META_OUTPUT:-$q6a/artifacts/dual-meta-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$out/embedded" "$out/phase"
timeout --signal=INT --kill-after=3s 15s \
    "$q6a/build/kernel-pdaf/capture-meta" /dev/video3 "$out/embedded" "$count" \
    > "$out/embedded/capture.log" 2>&1 &
embedded_pid=$!
timeout --signal=INT --kill-after=3s 15s \
    "$q6a/build/kernel-pdaf/capture-meta" /dev/video4 "$out/phase" "$count" \
    > "$out/phase/capture.log" 2>&1 &
phase_pid=$!
embedded_status=0
phase_status=0
wait "$embedded_pid" || embedded_status=$?
wait "$phase_pid" || phase_status=$?
printf 'Embedded status: %d; phase status: %d\n' "$embedded_status" "$phase_status"
printf 'Artifacts: %s\n' "$out"
tail -n 3 "$out/embedded/capture.log"
tail -n 3 "$out/phase/capture.log"
(( embedded_status == 0 && phase_status == 0 )) || exit 1
python3 "$here/analyze-meta.py" "$out/embedded" --image-width "$image_width" > "$out/embedded/meta.json"
python3 "$here/analyze-phase.py" "$out/phase" > "$out/phase/phase.json"
python3 "$here/pair-meta.py" "$out/embedded" "$out/phase" > "$out/pairing.json"
