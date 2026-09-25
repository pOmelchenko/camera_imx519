#!/usr/bin/env bash
# Compare captured VC0/DT0x36 PDAF samples at AK7375 positions.
# Run on Q6A with a fixed illuminated scene; the lens is restored after each sample.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
if (( $# == 0 )); then
    set -- 1024 2047 3072
fi
for position in "$@"; do
    [[ "$position" =~ ^[0-9]+$ ]] && (( position <= 4095 )) || {
        echo 'Focus positions must be raw AK7375 codes in 0..4095' >&2
        exit 2
    }
done
timeout --signal=INT --kill-after=3s 12s \
    cam -c 1 --stream role=raw,width=1920,height=1080 --capture=2 >/dev/null 2>&1
bash "$here/prepare-phase.sh"
out="$q6a/artifacts/phase-focus-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out"
for position in "$@"; do
    sample="$out/focus-$position"
    mkdir -p "$sample"
    python3 "$q6a/focus.py" "$position" -- \
        timeout --signal=INT --kill-after=3s 12s \
        "$q6a/build/kernel-pdaf/capture-meta" /dev/video4 "$sample" 8 \
        > "$sample/capture.log" 2>&1
    python3 "$here/analyze-phase.py" "$sample" > "$sample/phase.json"
    python3 "$here/analyze-phase.py" "$sample" --center > "$sample/phase-center.json"
    tail -n 2 "$sample/capture.log"
done
python3 "$here/estimate-phase-focus.py" "$out" > "$out/estimate.json"
cat "$out/estimate.json"
printf 'Artifacts: %s\n' "$out"
