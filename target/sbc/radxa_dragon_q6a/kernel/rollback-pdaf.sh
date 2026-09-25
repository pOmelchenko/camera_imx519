#!/usr/bin/env bash
# Restore the packaged qcom-camss module without replacing system files.
set -euo pipefail
expected=7.0.11-6-qcom
[[ "$(uname -r)" == "$expected" ]] || { echo 'Unexpected kernel release' >&2; exit 1; }
sudo -n true || { echo 'Run sudo -v in this terminal first.' >&2; exit 1; }
sudo -n modprobe -r qcom-camss
sudo -n modprobe qcom-camss
echo 'Packaged qcom-camss restored.'
