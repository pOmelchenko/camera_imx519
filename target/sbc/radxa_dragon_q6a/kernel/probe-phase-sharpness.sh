#!/usr/bin/env bash
# Compare phase-zero focus with two nearby manual positions on a fixed scene.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
candidate="${1:-}"
[[ "$candidate" =~ ^[0-9]+$ ]] && (( candidate >= 300 && candidate <= 3795 )) || {
    echo 'Usage: probe-phase-sharpness.sh CANDIDATE_RAW_CODE(300..3795)' >&2
    exit 2
}
out="$q6a/artifacts/phase-sharpness-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out"
images=()
for position in $((candidate - 300)) "$candidate" $((candidate + 300)); do
    bash "$q6a/snapshot.sh" "$position" > "$out/focus-$position.log" 2>&1
    source_image="$(sed -n 's/^Image: //p' "$out/focus-$position.log" | tail -n 1)"
    [[ -s "$source_image" ]] || { cat "$out/focus-$position.log" >&2; exit 1; }
    cp "$source_image" "$out/focus-$position.ppm"
    images+=("$out/focus-$position.ppm")
done
python3 "$q6a/score-focus.py" --roi 0.25 0.25 0.5 0.5 "${images[@]}" \
    > "$out/score.json"
cat "$out/score.json"
printf 'Artifacts: %s\n' "$out"
