#!/usr/bin/env bash
# Copy the built runtime to Radxa's home; no sudo, package replacement or reboot.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
(( $# <= 1 )) || { echo 'Usage: IMX519_SSH_TARGET=user@host deploy-runtime.sh [user@host]' >&2; exit 2; }
target="${1:-${IMX519_SSH_TARGET:-}}"
[[ -n "$target" && "$target" != -* ]] || { echo 'Set IMX519_SSH_TARGET=user@host or pass user@host.' >&2; exit 2; }
archive="$PWD/build/userspace/runtime.tar.gz"
digest="$(shasum -a 256 "$archive" | awk '{print $1}')"
[[ "$digest" =~ ^[0-9a-f]{64}$ ]]
bash sync-to-radxa.sh "$target"
ssh -o BatchMode=yes -o ConnectTimeout=10 "$target" 'mkdir -p ~/camera-imx519/build'
ssh -o BatchMode=yes "$target" "cat > ~/camera-imx519/build/runtime-$digest.tar.gz" < "$archive"
ssh -o BatchMode=yes "$target" "bash -s -- '$digest'" <<'REMOTE'
set -euo pipefail
cd ~/camera-imx519
digest="$1"
printf '%s  %s\n' "$digest" "build/runtime-$digest.tar.gz" | sha256sum -c -
[[ ! -e runtime/current || -L runtime/current ]] || { echo 'runtime/current is not a symlink.' >&2; exit 1; }
mkdir -p runtime
destination="$(mktemp -d "$PWD/runtime/imx519-${digest:0:12}.XXXXXX")"
tar -xzf "build/runtime-$digest.tar.gz" -C "$destination"
IMX519_RUNTIME="$destination" bash libcamera/run.sh cam -l 2>&1 | tee "$destination/first-camera-list.txt"
grep -q "External camera 'imx519'" "$destination/first-camera-list.txt"
if grep -Eiq "Configuration file 'imx519.yaml' not found|Failed to create camera sensor helper for imx519" "$destination/first-camera-list.txt"; then
    echo 'IMX519 support was not loaded; current runtime was not changed.' >&2
    exit 1
fi
ln -s "$(basename "$destination")" runtime/current.new
mv -Tf runtime/current.new runtime/current
printf 'Active private runtime: %s\n' "$destination"
REMOTE
