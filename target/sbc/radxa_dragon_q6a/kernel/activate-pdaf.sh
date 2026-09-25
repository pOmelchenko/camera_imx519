#!/usr/bin/env bash
# Run on Q6A after sudo -v. In-memory module swap; reboot or rollback restores stock.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
module="$here/../build/kernel-pdaf/drivers/media/platform/qcom/camss/qcom-camss.ko"
expected=7.0.11-6-qcom
[[ "$(uname -r)" == "$expected" ]] || { echo 'Unexpected kernel release' >&2; exit 1; }
[[ -f "$module" ]] || { echo "Missing staged module: $module" >&2; exit 1; }
[[ "$(modinfo -F vermagic "$module" | cut -d' ' -f1)" == "$expected" ]] || {
    echo 'Module vermagic does not match running kernel' >&2; exit 1;
}
sudo -n true || { echo 'Run sudo -v in this terminal first.' >&2; exit 1; }
stock="$(modinfo -n qcom-camss)"
[[ "$stock" == "/lib/modules/$expected/kernel/drivers/media/platform/qcom/camss/qcom-camss.ko.zst" ]] || {
    echo "Unexpected stock module path: $stock" >&2; exit 1;
}
rollback() {
    sudo -n modprobe -r qcom-camss || true
    sudo -n modprobe qcom-camss
}
trap rollback ERR
sudo -n modprobe -r qcom-camss
# modprobe -r may remove CAMSS-only dependencies; insmod does not reload them.
IFS=, read -r -a dependencies <<< "$(modinfo -F depends "$module")"
for dependency in "${dependencies[@]}"; do
    sudo -n modprobe "$dependency"
done
sudo -n insmod "$module"
trap - ERR
echo "Loaded experimental CAMSS module in memory: $(sha256sum "$module")"
echo 'Rollback: bash kernel/rollback-pdaf.sh (after sudo -v); reboot also restores stock.'
