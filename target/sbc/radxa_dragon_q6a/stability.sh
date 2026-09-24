#!/usr/bin/env bash
# Long capture without saving frames. Usage: stability.sh [rgb|raw] [count=9000]
# IMX519_TIMEOUT defaults to 420s; actual duration depends on the selected mode.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-rgb}"; count="${2:-9000}"; capture_timeout="${IMX519_TIMEOUT:-420}"
(( $# <= 2 )) || { echo 'Usage: stability.sh [rgb|raw] [count]' >&2; exit 2; }
for number in "$count" "$capture_timeout"; do
    [[ "$number" =~ ^[1-9][0-9]*$ ]] || { echo 'Count and timeout must be positive integers.' >&2; exit 2; }
done
case "$mode" in
    rgb) stream='role=viewfinder,width=1920,height=1080,pixelformat=XRGB8888' ;;
    raw) stream='role=raw,width=1920,height=1080' ;;
    *) echo 'Mode must be rgb or raw.' >&2; exit 2 ;;
esac
mkdir -p "$task_dir/artifacts"
run_dir="$(mktemp -d "$task_dir/artifacts/stability-$mode-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
command_args=(timeout --signal=INT --kill-after=3s "${capture_timeout}s"
    bash "$task_dir/cam.sh" -c /base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a
    --stream "$stream" "--capture=$count")
printf '%q ' "${command_args[@]}" > "$run_dir/command.txt"; printf '\n' >> "$run_dir/command.txt"
date -u +%FT%TZ > "$run_dir/start-utc.txt"
cat /proc/meminfo > "$run_dir/memory-before.txt"
printf 'Artifacts: %s\n' "$run_dir"
set +e
"${command_args[@]}" > "$run_dir/capture.log" 2>&1
status=$?
set -e
date -u +%FT%TZ > "$run_dir/end-utc.txt"
cat /proc/meminfo > "$run_dir/memory-after.txt"
printf '%s\n' "$status" > "$run_dir/exit-status"
(( status == 0 )) || { tail -30 "$run_dir/capture.log" >&2; exit "$status"; }
python3 - "$run_dir" "$count" <<'PY'
import json, re, sys
from pathlib import Path
p = Path(sys.argv[1]); expected = int(sys.argv[2])
log = (p / 'capture.log').read_text()
frames = [(float(t), int(s), int(b)) for t, s, b in re.findall(
    r'([\d.]+) \([^\n]*fps\) cam0-stream0 seq: (\d+) bytesused: (\d+)', log)]
gaps = sum(b[1] != a[1] + 1 for a, b in zip(frames, frames[1:]))
errors = [line for line in log.splitlines() if re.search(r'\bERROR\b|cancelled|timeout', line, re.I)]
elapsed = frames[-1][0] - frames[0][0] if len(frames) > 1 else 0
result = dict(frames=len(frames), expected=expected, seconds_between_first_last=elapsed,
              mean_fps=(len(frames)-1)/elapsed if elapsed else None,
              sequence_gaps=gaps, empty_frames=sum(b == 0 for _, _, b in frames), errors=errors)
ok = len(frames) == expected and gaps == 0 and not result['empty_frames'] and not errors
result['passed'] = ok
(p / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
if not ok:
    (p / 'exit-status').write_text('1\n')
    sys.exit(1)
PY
