#!/usr/bin/env bash
# Run on Q6A after loading the experimental CAMSS module; no sudo required.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
media="${IMX519_MEDIA_DEVICE:-/dev/media0}"
csid="$(media-ctl -d "$media" -e msm_csid0)"
vfe="$(media-ctl -d "$media" -e msm_vfe0_rdi1)"
video="$(media-ctl -d "$media" -e msm_vfe0_video1)"
[[ -c "$csid" && -c "$vfe" && -c "$video" ]] || {
    echo 'Expected CAMSS media nodes are missing.' >&2
    exit 1
}
cc -O2 -Wall -Wextra "$here/set-meta-formats.c" -o "$here/../build/kernel-pdaf/set-meta-formats"
media-ctl -d "$media" -l '"msm_csid0":2 -> "msm_vfe0_rdi1":0 [1]'
"$here/../build/kernel-pdaf/set-meta-formats" "$csid" "$vfe"
v4l2-ctl -d "$video" --set-fmt-meta=MET8 --get-fmt-meta
printf 'Metadata node: %s\n' "$video"
