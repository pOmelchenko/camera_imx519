# IMX519 autofocus on Dragon Q6A

Updated 2026-09-25 (Moscow). Target: Ubuntu 24.04.4, kernel `7.0.11-6-qcom`,
IMX519 on CAM3, AK7375 lens. This directory is the reproducible source package;
large build output and captures belong under the ignored `build/`, `artifacts/`
and repository `var/q6a-imx519/` directories.

## Result

The private `libcamera` simple pipeline now supports `AfModeManual`,
`AfModeAuto`, `AfModeContinuous`, `AfTrigger`, `AfPause`, `AfState` and
`LensPosition` through the simple software ISP. It uses horizontal green
gradient energy from RAW image statistics for contrast AF (CDAF). It scans
coarse and fine lens positions, waits 12 frames after each move, and rescans in
Continuous mode after a sustained drop in contrast. The lens subdevice remains
open through `CameraLens` for the camera lifetime, so the AK7375 runtime power
management does not park it between frames. The implementation is in
[`../libcamera/autofocus-simple.patch`](../libcamera/autofocus-simple.patch),
applied after the existing IMX519 helper patch. The
[manual-focus draft](https://patchwork.libcamera.org/patch/26241/) was used as a starting point;
the saved [`upstream-focus-reference.patch`](../libcamera/upstream-focus-reference.patch)
is that draft's mbox, not applied by the build.

The lens position mapping `0..15` dioptres to AK7375 raw `0..4095` is taken as
a **provisional** mapping from Arducam's Raspberry Pi IMX519 tuning. It is not
calibrated for the owner's 80° lens; `LensPosition` should not be used as a
measured distance yet. Existing `focus.py` raw-code workflows remain available:
in Manual mode the new runtime does not send lens commands until the client
explicitly supplies `LensPosition`.

## Phase-data blocker

Phase detection autofocus (PDAF) is **not implemented or validated** on Q6A.
The original `media-ctl -d /dev/media0 -p` topology on this board shows IMX519 pad 1 as
`unknown/17460x1` with **no outgoing link**, while pad 0 is linked to
`msm_csiphy3`. There is no userspace metadata capture node for this sensor.
The full read-only [media graph](../docs/evidence/2026-09-25-media-topology.txt)
is retained with the working kit.
Consequently libcamera cannot receive or pair per-frame phase samples. Merely
porting Arducam's Raspberry Pi AF algorithm would not supply missing samples.
An [experimental CAMSS patch](pdaf-bringup.md) now exposes a `MET8` node in
memory. A buffer-queue fault from the first attempt was fixed and
`REQBUFS`/`QUERYBUF` now pass, but no metadata frame has yet been delivered.
The camera still uses CDAF.

The installed `linux-image-7.0.11-6-qcom` package reports version `7.0.11-6`.
The matching [Radxa linux-qcom tag 7.0.11-6](https://github.com/radxa-pkg/linux-qcom/tree/7.0.11-6)
pins kernel source submodule `radxa/kernel` to
`657c0f722940cd9d3b51abfa7383655ec7d2c795`. This package saves its
[`camss-csid.c`](camss-csid-radxa-7.0.11-6.c) and
[`camss-vfe.c`](camss-vfe-radxa-7.0.11-6.c). Their format tables do not
include `MEDIA_BUS_FMT_SENSOR_DATA` or an embedded metadata capture format.
Their original URLs are [CSID](https://raw.githubusercontent.com/radxa/kernel/657c0f722940cd9d3b51abfa7383655ec7d2c795/drivers/media/platform/qcom/camss/camss-csid.c)
and [VFE](https://raw.githubusercontent.com/radxa/kernel/657c0f722940cd9d3b51abfa7383655ec7d2c795/drivers/media/platform/qcom/camss/camss-vfe.c);
SHA-256: `d81a9a75d251e586429e55007a1ce75dfc60d49603c2aa114035bbf10f683a51`
and `7cecb05f3da6bd012bbd5c00680ad7ec79fa4a16a5834ced7692147aaac48ec8`.
The live platform device reports compatible `qcom,sc7280-camss`.
The pinned [CAMSS resource table](camss-radxa-7.0.11-6.c)
(source [URL](https://raw.githubusercontent.com/radxa/kernel/657c0f722940cd9d3b51abfa7383655ec7d2c795/drivers/media/platform/qcom/camss/camss.c),
SHA-256 `873122ba4e82e7a56007ef7409c53e70870d44be9e3d168e65be3696f915daae`)
selects `csid_ops_gen2` for SC7280. That
[Gen2 CSID implementation](camss-csid-gen2-radxa-7.0.11-6.c)
(source [URL](https://raw.githubusercontent.com/radxa/kernel/657c0f722940cd9d3b51abfa7383655ec7d2c795/drivers/media/platform/qcom/camss/camss-csid-gen2.c),
SHA-256 `e41bb25cd436d0b997bab141e20d8b979343ee85f98038dd3e8951f78744a928`)
uses the RDI index as the CSI virtual channel and programs one data type from
the selected image format. If IMX519 phase data shares the image virtual
channel, capturing its additional embedded data type needs routing changes,
not just an IMX519 tuning file. The transmitted VC and payload remain to be
measured.
The current CSID format propagation copies its sink image format to the source;
VFE line formatting clamps height to at least four, while IMX519 advertises
one embedded line. A functional metadata path must address those format and
buffer contracts and then provide a paired buffer to libcamera. The
experimental module addresses the format setup but has not passed the buffer
capture gate; it has not replaced the packaged module on disk.

To complete PDAF, patch this pinned kernel and confirm the sensor actually
emits phase-bearing CSI
embedded data in each active mode, expose that stream through IMX519 and
QCOM CAMSS CSID/VFE as a metadata video node, preserve sequence/timestamp
pairing with image frames, then parse and calibrate the phase grid in the IPA.
The [IMX519 PDAF parser proposal](https://lists.libcamera.org/pipermail/libcamera-devel/2023-June/038275.html)
describes a Raspberry Pi format; it cannot be assumed correct on Q6A without
captured bytes. Test near/far phase sign and confidence on the physical module
before enabling phase-based lens moves.

## Build and hardware evidence

- Source: `radxa-pkg/libcamera` commit
  `de1e9bc095e23085e77533357d2582176de0a582`, the saved Radxa Debian
  patch series, `imx519.patch`, then `autofocus-simple.patch` (SHA-256
  `fd25bd5842f392c617ddaf63b143f570d019fe41c4ef25b5bf68a18aa3e4fbae`).
- Docker Ubuntu 24.04 arm64 build succeeded; `meson test --suite ipa` reported
  8 passed, 0 failed. Active private runtime archive SHA-256
  `989d44efdfd20091514a1c9607c10a1e8f9b0758ada8b7438c38c7c125423f03`.
  It is deployed under `~/camera-imx519/runtime/`; system libcamera packages,
  DKMS modules and boot overlay were not replaced.
- A 640×480 Continuous run (360 frames) reported `AfStateScanning` then
  `AfStateFocused`, selecting raw code 2174. In the same stationary scene,
  1080p manual captures at 2174 and 2496 scored respectively 0.002955 and
  0.001663 using `score-focus.py`'s fixed ROI. This is a scene-specific
  sharpness check, not a lens calibration.
- A 1080p Continuous run (360 frames) reached Focused at raw code 2047. On the
  final build, an Auto script triggered two scans in one stream, finishing at
  raw codes 2047 and 2174. Manual `LensPosition: 9.14` was read back via V4L2
  as `focus_absolute: 2495`. Continuous `AfPauseImmediate` and
  `AfPauseResume` produced 40 paused and 320 running frames in a 360-frame
  stream. See `var/q6a-imx519/` for retained captures and logs.
- The final 1080p Continuous run captured 1800 frames in 59.966 seconds
  (30.000 fps average), with contiguous sequence numbers 0..1799 and no
  libcamera errors. It completed three contrast scans at raw code 2047.
  `snapshot-af.sh auto` then produced a 1080p PPM after 360 frames; final
  state was Focused at raw code 2174. The copied image and capture log are
  `var/q6a-imx519/autofocus-1080p.{ppm,log}`; parsed results are in
  `var/q6a-imx519/af-summary.json`.

Run the checks using `cam.sh` and the `libcamera/af-*.yaml` scripts. For a
single AF photograph on the board run `bash snapshot-af.sh auto`. For a
read-only return to the previous runtime, set
`IMX519_RUNTIME=/home/radxa/camera-imx519/runtime/imx519-48c432913b9e.E1ywoR`
before `bash cam.sh ...`; `IMX519_LIBCAMERA=system` selects the apt build.

## Remaining qualification

The current image contrast metric covers the full sampled RAW frame; region
selection, optical distance calibration, low-light/flat-scene failure, moving
subject reacquisition and restart after a reboot need separate physical
checks. PDAF requires the metadata path above. Do not label
the stack phase autofocus capable until phase samples and phase-driven focus
are observed on this board.
