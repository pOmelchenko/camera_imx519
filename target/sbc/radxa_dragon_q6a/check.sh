#!/usr/bin/env bash
set -u
printf '\nKernel: '; uname -r
printf '\nCamera driver messages:\n'
if (( EUID == 0 )); then
    kernel_log="$(dmesg)"
else
    kernel_log="$(journalctl -k -b --no-pager 2>/dev/null)"
fi
printf '%s\n' "$kernel_log" | grep -iE 'imx519|ak7375|camss|csiphy|csid|vfe' || true
printf '\nKernel warning / error context (all drivers):\n'
printf '%s\n' "$kernel_log" | grep -A55 -B10 -E 'WARNING:|BUG:|Oops:|Call trace:|Modules linked in' || true
printf '\nI2C sensor and lens bindings:\n'
for device in /sys/bus/i2c/devices/*; do
    [[ -f "$device/name" ]] || continue
    name="$(cat "$device/name")"
    if [[ "$name" == imx519 || "$name" == ak7375 ]]; then
        printf '%s: %s, driver=%s\n' "$device" "$name" "$(readlink "$device/driver" || true)"
    fi
done
printf '\nV4L2 devices:\n'
v4l2-ctl --list-devices
printf '\nMedia topology:\n'
for media in /dev/media*; do
    [[ -e "$media" ]] || continue
    media-ctl -d "$media" -p
done
printf '\nLibcamera cameras:\n'
bash "$(dirname -- "${BASH_SOURCE[0]}")/cam.sh" -l
