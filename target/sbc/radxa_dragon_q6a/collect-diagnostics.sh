#!/usr/bin/env bash
# Read-only snapshot; no capture, package installation, module reload or reboot.
# Usage: bash collect-diagnostics.sh [output-parent]
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    sed -n '2,3p' "${BASH_SOURCE[0]}"
    exit 0
fi
(( $# <= 1 )) || { echo 'Too many arguments; use --help.' >&2; exit 2; }
output_parent="${1:-$task_dir/artifacts}"
mkdir -p "$output_parent"
run_dir="$(mktemp -d "$output_parent/diagnostics-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
run_dir="$(cd "$run_dir" && pwd)"
record() {
    local filename="$1" status=0
    shift
    {
        printf 'Command: '; printf '%q ' "$@"; printf '\n\n'
        "$@" || status=$?
        printf '\nExit status: %s\n' "$status"
    } > "$run_dir/$filename" 2>&1
    printf '%s\t%s\n' "$status" "$filename" >> "$run_dir/status.tsv"
}
record utc.txt date -u +%FT%TZ
record uname.txt uname -a
record os-release.txt cat /etc/os-release
record identity.txt id
record versions.txt dpkg-query -W libcamera-tools libcamera-ipa libcamera0.7 v4l-utils radxa-overlays-dkms rsetup
record dkms.txt dkms status
record imx519-module.txt modinfo imx519
record ak7375-module.txt modinfo ak7375
record cameras.txt timeout 15s bash "$task_dir/cam.sh" -l
record cameras-system.txt timeout 15s cam -l
if [[ -d "$task_dir/runtime/current" ]]; then
    record runtime-version.txt cat "$task_dir/runtime/current/version.txt" "$task_dir/runtime/current/source-revision.txt"
fi
record video-devices.txt v4l2-ctl --list-devices
record source-hashes.txt bash -c 'cd "$1" && sha256sum -c SOURCES.sha256' _ "$task_dir"
record config.txt bash -c 'grep -E "CONFIG_VIDEO_(IMX519|AK7375|QCOM_CAMSS)|CONFIG_CMA" "/boot/config-$(uname -r)"'
shopt -s nullglob
for media in /dev/media*; do
    record "$(basename "$media")-topology.txt" media-ctl -d "$media" -p
done
for subdev in /sys/class/video4linux/v4l-subdev*; do
    name="$(cat "$subdev/name")"
    case "$name" in
        imx519*|ak7375*) record "$(basename "$subdev")-controls.txt" v4l2-ctl -d "/dev/$(basename "$subdev")" --list-ctrls ;;
    esac
done
record permissions.txt ls -l /dev/media* /dev/video* /dev/v4l-subdev* /dev/dma_heap/*
if (( EUID == 0 )); then
    record kernel-full.txt dmesg
else
    # Uses an existing sudo timestamp; never asks for a password in this script.
    record kernel-full.txt sudo -n dmesg
fi
record check.txt bash "$task_dir/check.sh"
printf 'Diagnostics: %s\n' "$run_dir"
printf '%s\n' 'Nonzero commands (including unavailable privileged kernel log):'
awk -F '\t' '$1 != 0 { print }' "$run_dir/status.tsv"
printf '%s\n' 'For full kernel log: run sudo -v in this terminal, then rerun this script.'
