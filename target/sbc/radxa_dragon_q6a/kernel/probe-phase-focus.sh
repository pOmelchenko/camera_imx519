#!/usr/bin/env bash
# Compare captured VC0/DT0x36 PDAF samples at two AK7375 positions.
# Run on Q6A after sudo -v, with a fixed illuminated scene.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
parameter=/sys/module/qcom_camss/parameters/probe_phase_dt36
[[ -f "$parameter" ]] || { echo 'Load the diagnostic CAMSS module first.' >&2; exit 1; }
sudo -n true || { echo 'Run sudo -v in this terminal first.' >&2; exit 1; }
[[ "$(sudo -n cat "$parameter")" == N ]] || {
    echo 'Phase probe is already enabled; refusing to change its state.' >&2
    exit 1
}
restore() { printf N | sudo -n tee "$parameter" >/dev/null; }
trap restore EXIT
printf Y | sudo -n tee "$parameter" >/dev/null
bash "$here/prepare-meta.sh"
out="$q6a/artifacts/phase-focus-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out"
for position in 2047 2496; do
    sample="$out/focus-$position"
    mkdir -p "$sample"
    python3 "$q6a/focus.py" "$position" -- \
        timeout --signal=INT --kill-after=3s 12s \
        "$q6a/build/kernel-pdaf/capture-meta" /dev/video3 "$sample" 8 \
        > "$sample/capture.log" 2>&1
    python3 "$here/analyze-phase.py" "$sample" > "$sample/phase.json"
    tail -n 2 "$sample/capture.log"
done
printf 'Artifacts: %s\n' "$out"
