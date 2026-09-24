#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob
export LC_ALL=C
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
task_dir="$PWD"
kernel="$(uname -r)"
overlay=qcs6490-radxa-dragon-q6a-cam3-imx519.dtbo
package=arducam-imx519-q6a
version=0.1.0

if (( EUID != 0 )); then
    printf '%s\n' 'Run: sudo bash ~/camera-imx519/install.sh' >&2
    exit 1
fi
if [[ "$(tr -d '\0' </proc/device-tree/model)" != 'Radxa Dragon Q6A' ]]; then
    echo 'This installer is only for Radxa Dragon Q6A.' >&2
    exit 1
fi
if [[ "$kernel" != 7.0.11-6-qcom || "$(cat build/kernel-release)" != "$kernel" ]]; then
    echo 'This package was validated for 7.0.11-6-qcom. Revalidate before using another kernel.' >&2
    exit 1
fi
test -s "build/$overlay"
test -s driver/imx519.ko
test -s driver/ak7375.ko

# Use the same boot-directory discovery and update functions as rsetup.
DEBUG=false
FDT_OVERLAYS_DIR=
U_BOOT_FDT_OVERLAYS_DIR=
source /usr/lib/rsetup/cli/main.sh
load_overlay_setting
if [[ -d /sys/firmware/efi ]] && ! is_edk2_exist; then
    echo 'Cannot locate active EFI loader entry; no installation performed.' >&2
    exit 1
fi
overlay_dirs=()
if [[ -n "$U_BOOT_FDT_OVERLAYS_DIR" ]]; then
    overlay_dirs+=("$(realpath "$U_BOOT_FDT_OVERLAYS_DIR")")
fi
if [[ -n "$FDT_OVERLAYS_DIR" ]]; then
    current_dir="$(realpath "$FDT_OVERLAYS_DIR")"
    if [[ "$current_dir" != "${overlay_dirs[0]:-}" ]]; then
        overlay_dirs+=("$current_dir")
    fi
fi
(( ${#overlay_dirs[@]} > 0 ))

# Do not enable two sensors on the same CAM3 I2C bus / enable pin.
for overlay_dir in "${overlay_dirs[@]}"; do
    test -d "$overlay_dir"
    for active in "$overlay_dir"/*.dtbo; do
        [[ "$(basename "$active")" != "$overlay" ]] || continue
        resources="$(fdtget -t s "$active" /metadata exclusive 2>/dev/null || true)"
        for resource in $resources; do
            if [[ "$resource" == cci1_i2c1 || "$resource" == gpio78 ]]; then
                echo "CAM3 conflict: $active. Disable it in rsetup first." >&2
                exit 1
            fi
        done
    done
done

source_dir="/usr/src/$package-$version"
source_files=(imx519.c ak7375.c Makefile dkms.conf)
if [[ -e "$source_dir" ]]; then
    for filename in "${source_files[@]}"; do
        if ! cmp -s "driver/$filename" "$source_dir/$filename"; then
            echo "Existing DKMS source differs: $source_dir/$filename" >&2
            exit 1
        fi
    done
fi

apt-get install -y dkms v4l-utils libcamera-tools libcamera-ipa
install -d "$source_dir"
for filename in "${source_files[@]}"; do
    install -m 0644 "driver/$filename" "$source_dir/$filename"
done
if ! dkms status -m "$package" -v "$version" | grep -q .; then
    dkms add -m "$package" -v "$version"
fi
dkms install -m "$package" -v "$version" -k "$kernel"
depmod "$kernel"

backup="$(mktemp -d /var/backups/imx519-cam3.XXXXXXXX)"
printf '%s\n' "${overlay_dirs[@]}" > "$backup/overlay-directories.txt"
if [[ -d /boot/efi/loader/entries ]]; then
    cp -a /boot/efi/loader/entries "$backup/efi-loader-entries"
fi
if [[ -f /boot/extlinux/extlinux.conf ]]; then
    cp -a /boot/extlinux/extlinux.conf "$backup/extlinux.conf"
fi
index=0
for overlay_dir in "${overlay_dirs[@]}"; do
    cp -a "$overlay_dir" "$backup/overlays-$index"
    index=$((index + 1))
done
printf 'Boot configuration backup: %s\n' "$backup"

for overlay_dir in "${overlay_dirs[@]}"; do
    install -m 0644 "$task_dir/build/$overlay" "$overlay_dir/$overlay"
done
update_overlay_entry

printf '\n%s\n' \
    'Installed IMX519 and AK7375 drivers and enabled CAM3 overlay.' \
    'Reboot when ready: sudo reboot' \
    'After reboot: sudo bash ~/camera-imx519/check.sh' \
    'After reboot, validate this installation: bash ~/camera-imx519/capture.sh raw' \
    'Automatic focus and calibrated colour processing remain unvalidated.'
