#!/usr/bin/env bash
# Diagnostic capture of IMX519 VC0/DT0x36 on RDI1, restoring DT0x12 on exit.
# Run on Q6A after loading the experimental CAMSS module and sudo -v.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
parameter=/sys/module/qcom_camss/parameters/probe_phase_dt36
[[ -f "$parameter" ]] || {
    echo "Loaded CAMSS module lacks $parameter" >&2
    exit 1
}
sudo -n true || { echo 'Run sudo -v in this terminal first.' >&2; exit 1; }
[[ "$(sudo -n cat "$parameter")" == N ]] || {
    echo 'Phase probe is already enabled; refusing to change its state.' >&2
    exit 1
}
restore() {
    printf N | sudo -n tee "$parameter" >/dev/null
}
trap restore EXIT
printf Y | sudo -n tee "$parameter" >/dev/null
bash "$here/probe-meta-registers.sh" meta
