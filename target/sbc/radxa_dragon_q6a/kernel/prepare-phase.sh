#!/usr/bin/env bash
# Configure simultaneous IMX519 embedded (RDI1) and PDAF (RDI2) routes.
# Run on Q6A with the experimental CAMSS module; no sudo required.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
media="${IMX519_MEDIA_DEVICE:-/dev/media0}"
sensor="$(media-ctl -d "$media" -e "${IMX519_SENSOR_ENTITY:-imx519 20-001a}")"
csiphy="$(media-ctl -d "$media" -e msm_csiphy3)"
csid="$(media-ctl -d "$media" -e msm_csid0)"
vfe1="$(media-ctl -d "$media" -e msm_vfe0_rdi1)"
vfe2="$(media-ctl -d "$media" -e msm_vfe0_rdi2)"
video1="$(media-ctl -d "$media" -e msm_vfe0_video1)"
video2="$(media-ctl -d "$media" -e msm_vfe0_video2)"
for node in "$sensor" "$csiphy" "$csid" "$vfe1" "$vfe2" "$video1" "$video2"; do
    [[ -c "$node" ]] || { echo "Missing CAMSS media node: $node" >&2; exit 1; }
done
cc -O2 -Wall -Wextra "$here/set-meta-formats.c" -o "$here/../build/kernel-pdaf/set-meta-formats"
media-ctl -d "$media" -l '"msm_csiphy3":1 -> "msm_csid0":0 [1]'
media-ctl -d "$media" -l '"msm_csid0":2 -> "msm_vfe0_rdi1":0 [1]'
media-ctl -d "$media" -l '"msm_csid0":3 -> "msm_vfe0_rdi2":0 [1]'
"$here/../build/kernel-pdaf/set-meta-formats" "$sensor" "$csiphy" "$csid" "$vfe1" "$vfe2"
v4l2-ctl -d "$video1" --set-fmt-meta=MET8 --get-fmt-meta
v4l2-ctl -d "$video2" --set-fmt-meta=MET8 --get-fmt-meta
printf 'Embedded node: %s; phase node: %s\n' "$video1" "$video2"
