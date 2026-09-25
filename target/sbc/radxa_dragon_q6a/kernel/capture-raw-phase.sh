#!/usr/bin/env bash
# Exercise concurrent full-resolution RAW10 and IMX519 PDAF capture on Q6A.
# The RAW frames are discarded; small phase buffers and logs are saved.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
out="$q6a/artifacts/raw-phase-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out/phase"
timeout --signal=INT --kill-after=3s 12s \
    cam -c 1 --stream role=raw,width=4656,height=3496 --capture=2 \
    > "$out/raw-setup.log" 2>&1
bash "$here/prepare-phase.sh" > "$out/prepare.log"
v4l2-ctl -d /dev/video2 --get-fmt-video > "$out/raw-format.txt"
grep -q '4656/3496' "$out/raw-format.txt"
timeout --signal=INT --kill-after=3s 10s \
    v4l2-ctl -d /dev/video2 --stream-mmap=2 --stream-count=48 \
    > "$out/raw.log" 2>&1 &
raw_pid=$!
sleep 1
phase_status=0
timeout --signal=INT --kill-after=3s 10s \
    "$q6a/build/kernel-pdaf/capture-meta" /dev/video4 "$out/phase" 24 \
    > "$out/phase/capture.log" 2>&1 || phase_status=$?
raw_status=0
wait "$raw_pid" || raw_status=$?
printf 'RAW status: %d; phase status: %d\n' "$raw_status" "$phase_status"
printf 'Artifacts: %s\n' "$out"
tail -n 3 "$out/raw.log"
tail -n 3 "$out/phase/capture.log"
(( raw_status == 0 && phase_status == 0 )) || exit 1
python3 "$here/analyze-phase.py" "$out/phase" > "$out/phase/phase.json"
