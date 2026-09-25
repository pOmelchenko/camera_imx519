#!/usr/bin/env bash
# Rebuild only qcom-camss for the pinned Q6A kernel and stage it in the board home.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
q6a="$(dirname "$here")"
source_tree="${IMX519_KERNEL_SOURCE:-$q6a/vendor/kernel}"
target="${1:-${IMX519_SSH_TARGET:-}}"
commit=657c0f722940cd9d3b51abfa7383655ec7d2c795
kernel_release=7.0.11-6-qcom
[[ -n "$target" && "$target" != -* ]] || {
    echo 'Usage: IMX519_SSH_TARGET=user@host build-and-stage.sh [user@host]' >&2
    exit 2
}
[[ "$(git -C "$source_tree" rev-parse HEAD)" == "$commit" ]] || {
    echo "Expected pinned radxa/kernel commit $commit in $source_tree" >&2
    exit 1
}
stage="$(mktemp -d "${TMPDIR:-/tmp}/imx519-camss.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
mkdir -p "$stage/drivers/media/platform/qcom"
cp -R "$source_tree/drivers/media/platform/qcom/camss" "$stage/drivers/media/platform/qcom/"
git -C "$source_tree" diff -- drivers/media/platform/qcom/camss > "$stage/source.diff"
if [[ -s "$stage/source.diff" ]]; then
    cmp -s "$stage/source.diff" "$here/camss-pdaf.patch" || {
        echo 'CAMSS source has changes other than the recorded PDAF patch.' >&2
        exit 1
    }
    (cd "$stage" && git apply --reverse "$here/camss-pdaf.patch")
fi
(cd "$stage" && git apply --check "$here/camss-pdaf.patch" && git apply "$here/camss-pdaf.patch")
export COPYFILE_DISABLE=1
tar_options=()
if [[ "$(uname -s)" == Darwin ]]; then
    tar_options+=(--no-xattrs --no-acls --no-fflags)
fi
ssh -o BatchMode=yes -o ConnectTimeout=10 "$target" \
    'mkdir -p ~/camera-imx519/build/kernel-pdaf'
tar "${tar_options[@]}" -C "$stage" -cf - drivers/media/platform/qcom/camss | \
    ssh -o BatchMode=yes "$target" \
        'tar -xf - -C ~/camera-imx519/build/kernel-pdaf'
ssh -o BatchMode=yes "$target" "bash -s -- '$kernel_release'" <<'REMOTE'
set -euo pipefail
expected="$1"
[[ "$(uname -r)" == "$expected" ]] || { echo 'Unexpected kernel release' >&2; exit 1; }
module_dir="$HOME/camera-imx519/build/kernel-pdaf/drivers/media/platform/qcom/camss"
make -C "/lib/modules/$expected/build" M="$module_dir" modules -j4
[[ "$(modinfo -F vermagic "$module_dir/qcom-camss.ko" | cut -d' ' -f1)" == "$expected" ]]
sha256sum "$module_dir/qcom-camss.ko"
REMOTE
