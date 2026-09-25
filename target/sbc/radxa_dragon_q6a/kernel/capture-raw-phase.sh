#!/usr/bin/env bash
# Exercise concurrent native RAW10 and IMX519 PDAF capture on Q6A.
# The RAW frames are discarded; small phase buffers and logs are saved.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
mode="${1:-4656x3496}"
case "$mode" in
    4656x3496) fps=9 ;;
    3840x2160) fps=18 ;;
    2328x1748) fps=30 ;;
    1920x1080) fps=60 ;;
    1280x720) fps=80 ;;
    *) echo 'Usage: capture-raw-phase.sh [NATIVE_MODE]' >&2; exit 2 ;;
esac
width="${mode%x*}"
height="${mode#*x}"
raw_count=$((fps * 4))
phase_count=$((fps * 2))
out="$q6a/artifacts/raw-phase-$mode-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out/phase"
timeout --signal=INT --kill-after=3s 12s \
    cam -c 1 --stream "role=raw,width=$width,height=$height" --capture=2 \
    > "$out/raw-setup.log" 2>&1
bash "$here/prepare-phase.sh" > "$out/prepare.log"
v4l2-ctl -d /dev/video2 --get-fmt-video > "$out/raw-format.txt"
grep -q "$width/$height" "$out/raw-format.txt"
cc -O2 -Wall -Wextra "$here/capture-raw-timestamps.c" \
    -o "$q6a/build/kernel-pdaf/capture-raw-timestamps"
timeout --signal=INT --kill-after=3s 10s \
    "$q6a/build/kernel-pdaf/capture-raw-timestamps" \
    /dev/video2 "$out/raw-frames.csv" "$raw_count" \
    > "$out/raw.log" 2>&1 &
raw_pid=$!
sleep 0.5
phase_status=0
timeout --signal=INT --kill-after=3s 10s \
    "$q6a/build/kernel-pdaf/capture-meta" /dev/video4 "$out/phase" "$phase_count" \
    > "$out/phase/capture.log" 2>&1 || phase_status=$?
raw_status=0
wait "$raw_pid" || raw_status=$?
printf 'RAW status: %d; phase status: %d\n' "$raw_status" "$phase_status"
printf 'Artifacts: %s\n' "$out"
tail -n 3 "$out/raw-frames.csv"
tail -n 3 "$out/phase/capture.log"
(( raw_status == 0 && phase_status == 0 )) || exit 1
python3 "$here/analyze-phase.py" "$out/phase" > "$out/phase/phase.json"
python3 "$here/pair-image-phase.py" "$out" > "$out/pairing.json"
