#!/usr/bin/env bash
# Check whether an interpolated focus code actually drives central phase to zero.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
sweep="${1:-}"
[[ -f "$sweep/estimate.json" ]] || {
    echo 'Usage: verify-phase-candidate.sh PHASE_FOCUS_ARTIFACT' >&2
    exit 2
}
candidate="$(python3 - "$sweep/estimate.json" <<'PY'
import json
import sys
estimate = json.load(open(sys.argv[1]))
if estimate['status'] != 'bracketed':
    raise SystemExit('No bracketed phase-zero candidate')
print(estimate['candidate_raw_code'])
PY
)"
candidate="${2:-$candidate}"
[[ "$candidate" =~ ^[0-9]+$ ]] && (( candidate <= 4095 )) || {
    echo 'Candidate must be a raw AK7375 code in 0..4095' >&2
    exit 2
}
out="$sweep/candidate-$candidate"
mkdir -p "$out"
timeout --signal=INT --kill-after=3s 12s \
    cam -c 1 --stream role=raw,width=1920,height=1080 --capture=2 >/dev/null 2>&1
bash "$here/prepare-phase.sh" > "$out/prepare.log"
python3 "$q6a/focus.py" "$candidate" -- \
    timeout --signal=INT --kill-after=3s 12s \
    "$q6a/build/kernel-pdaf/capture-meta" /dev/video4 "$out" 16 \
    > "$out/capture.log" 2>&1
python3 "$here/analyze-phase.py" "$out" --center > "$out/phase-center.json"
python3 "$here/analyze-phase.py" "$out" > "$out/phase.json"
python3 - "$out/phase-center.json" "$candidate" <<'PY'
import json
import statistics
import sys
frames = json.load(open(sys.argv[1]))['frames']
phases = [frame['median_phase'] for frame in frames]
confidence = [frame['qualified_regions'] for frame in frames]
if any(value is None for value in phases):
    raise SystemExit('No central phase in some frames')
print(f'Candidate {sys.argv[2]}: central median phase '
      f'{statistics.median(phases)}, range {min(phases)}..{max(phases)}, '
      f'qualified regions {min(confidence)}..{max(confidence)}')
PY
printf 'Artifacts: %s\n' "$out"
