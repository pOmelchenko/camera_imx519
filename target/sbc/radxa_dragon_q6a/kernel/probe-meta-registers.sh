#!/usr/bin/env bash
# Read CAMSS configuration while a bounded MET8 or RAW capture powers the block.
# Run on Q6A after sudo -v. Pass raw to compare the working RAW path.
set -u
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
stream="${1:-meta}"
if [[ "$stream" != meta && "$stream" != raw ]]; then
    echo 'Usage: probe-meta-registers.sh [meta|raw]' >&2
    exit 2
fi
sudo -n true || { echo 'Run sudo -v in this terminal first.' >&2; exit 1; }
if [[ "$stream" == meta ]]; then
    bash "$here/prepare-meta.sh" || exit 1
fi
out="$q6a/artifacts/pdaf-registers-$stream-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out"
printf 'Artifacts: %s\n' "$out"
grep -E 'csid0|vfe0|csiphy3' /proc/interrupts > "$out/interrupts-before.txt"
if [[ "$stream" == meta ]]; then
    timeout --signal=INT --kill-after=3s 9s \
        "$q6a/build/kernel-pdaf/capture-meta" /dev/video3 "$out" 16 \
        > "$out/capture.log" 2>&1 &
else
    timeout --signal=INT --kill-after=3s 9s \
        cam -c 1 --stream role=raw,width=4656,height=3496 --capture=1000 \
        > "$out/capture.log" 2>&1 &
fi
capture_pid=$!
sleep 1
if kill -0 "$capture_pid" 2>/dev/null; then
    sudo -n python3 "$here/read-camss-registers.py" > "$out/registers.txt" 2>&1
    register_status=$?
    sleep 1
    if kill -0 "$capture_pid" 2>/dev/null; then
        sudo -n python3 "$here/read-camss-registers.py" > "$out/registers-second.txt" 2>&1
        second_status=$?
        if (( register_status == 0 )); then
            register_status=$second_status
        fi
    fi
else
    echo 'Capture exited before MMIO sample' > "$out/registers.txt"
    register_status=1
fi
wait "$capture_pid"
capture_status=$?
grep -E 'csid0|vfe0|csiphy3' /proc/interrupts > "$out/interrupts-after.txt"
printf 'Register read status: %d; capture status: %d\n' "$register_status" "$capture_status"
cat "$out/registers.txt"
if [[ -f "$out/registers-second.txt" ]]; then
    echo 'Second sample:'
    cat "$out/registers-second.txt"
fi
tail -n 8 "$out/capture.log"
if [[ "$stream" == meta ]]; then
    printf 'Completed metadata frames: '
    if [[ -f "$out/frames.csv" ]]; then
        awk 'END { print NR - 1 }' "$out/frames.csv"
    else
        echo 0
    fi
fi
exit "$register_status"
