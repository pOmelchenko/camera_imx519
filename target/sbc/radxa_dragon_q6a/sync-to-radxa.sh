#!/usr/bin/env bash
# Copy source and documentation only. Does not install drivers or alter boot.
# Usage on the workstation: IMX519_SSH_TARGET=user@host bash sync-to-radxa.sh
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    sed -n '2,3p' "${BASH_SOURCE[0]}"
    exit 0
fi
(( $# <= 1 )) || { echo 'Too many arguments.' >&2; exit 2; }
target="${1:-${IMX519_SSH_TARGET:-}}"
[[ -n "$target" && "$target" != -* ]] || { echo 'Set IMX519_SSH_TARGET=user@host or pass user@host.' >&2; exit 2; }
archive="$(mktemp "${TMPDIR:-/tmp}/imx519-sync.XXXXXXXX")"
trap 'rm -f -- "$archive"' EXIT
# macOS tar otherwise adds AppleDouble files (._*) to the Linux destination.
export COPYFILE_DISABLE=1
tar_options=()
if [[ "$(uname -s)" == Darwin ]]; then
    tar_options+=(--no-xattrs --no-acls --no-fflags)
fi
tar "${tar_options[@]}" -cf "$archive" .gitignore README.md SOURCES.sha256 docs libcamera research kernel \
    build.sh install.sh check.sh cam.sh capture.sh focus.py focus-sweep.sh score-focus.py af-log-summary.py stability.sh color-five-modes.sh \
    collect-diagnostics.sh disable-autosuspend.sh snapshot.sh snapshot-af.sh preview.sh focus-position.txt sync-to-radxa.sh \
    driver/imx519.c driver/ak7375.c driver/Makefile driver/dkms.conf \
    overlays/qcs6490-radxa-dragon-q6a-cam3-imx519.dts
ssh -o BatchMode=yes -o ConnectTimeout=10 "$target" \
    'mkdir -p ~/camera-imx519 && tar -xf - -C ~/camera-imx519' < "$archive"
printf 'Sources and documentation copied to %s:~/camera-imx519\n' "$target"
