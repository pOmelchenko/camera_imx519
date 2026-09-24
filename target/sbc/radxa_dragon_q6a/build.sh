#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
kernel="$(uname -r)"
headers="/lib/modules/$kernel/build"
overlay=qcs6490-radxa-dragon-q6a-cam3-imx519
base="/usr/lib/linux-image-$kernel/qcom/qcs6490-radxa-dragon-q6a.dtb"
test -d "$headers"
test -f "$base"
sha256sum -c SOURCES.sha256
mkdir -p build
make -C "$headers" M="$PWD/driver" -j2 modules
cpp -nostdinc -undef -x assembler-with-cpp -E -I "$headers/include" \
    "overlays/$overlay.dts" > "build/$overlay.pp.dts"
dtc -@ -I dts -O dtb -o "build/$overlay.dtbo" "build/$overlay.pp.dts"
fdtoverlay -i "$base" -o build/q6a-imx519-validation.dtb "build/$overlay.dtbo"
test "$(fdtget build/q6a-imx519-validation.dtb /soc@0/cci@ac4b000/i2c-bus@1/camera@1a compatible)" = sony,imx519
test "$(fdtget build/q6a-imx519-validation.dtb /soc@0/isp@acb3000 status)" = okay
modinfo -F vermagic driver/imx519.ko
modinfo -F vermagic driver/ak7375.ko
printf '%s\n' "$kernel" > build/kernel-release
printf '%s\n' 'Build and device-tree merge passed. Use capture.sh to validate hardware on this installation.'
