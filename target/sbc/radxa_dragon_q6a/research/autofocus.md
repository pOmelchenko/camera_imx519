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

## Phase-data status

Phase detection autofocus (PDAF) is **not yet integrated into libcamera** on
Q6A. The original `media-ctl -d /dev/media0 -p` topology showed IMX519 pad 1
as `unknown/17460x1` with no outgoing link, while pad 0 was linked to
`msm_csiphy3`. The stock CAMSS exposed no metadata capture node.
The full read-only [media graph](../docs/evidence/2026-09-25-media-topology.txt)
is retained with the working kit. The experimental CAMSS module now exposes
metadata nodes; a later private libcamera runtime pairs their phase frames
with RAW by timestamp.
An [experimental CAMSS patch](pdaf-bringup.md) now exposes a `MET8` node in
memory. A buffer-queue fault and an RDI1/write-master mapping error were
fixed. MET8 now delivers frames at 9 fps in the full-resolution mode and
60 fps at 1920×1080. The first two embedded-data rows are VC0/DT `0x12`.
A separate VC0/DT `0x36` packet contains the PDAF row. Sixteen consecutive
phase buffers were parsed as a 12×16 grid; moving the AK7375 from code 2047
to 2496 shifted median phase from about −17 to +44 on the same scene.
An independent RDI2 now captures phase concurrently with RDI1 embedded data
in all five native modes. Short RAW+phase runs completed in all five modes
after the VFE stop fix, with unique timestamp pairing and no sequence gaps.
An external one-shot controller performs phase-driven lens moves and takes a
color picture after convergence; its
[evidence](../docs/evidence/2026-09-25-snapshot-pdaf.json) also compares
optical sharpness at adjacent lens codes. A later private libcamera runtime
feeds center-grid phase into the simple IPA and moves the lens during color
streaming. Auto and Continuous reached phase focus on one lit fixed scene.
A mixed-depth scene produced unstable phase and fell back to CDAF. The
[in-stream evidence](../docs/evidence/2026-09-25-libcamera-pdaf.json) records
the moves and manual sharpness controls.

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
not just an IMX519 tuning file. The observed packets are VC0/DT `0x12` for
two embedded rows and VC0/DT `0x36` for the PDAF row.
The original CSID/VFE format propagation copied the image format and clamped
metadata height. The experimental module now exposes the two actual embedded
rows and separate phase row with buffer lengths derived from the selected
RAW10 width. Short simultaneous embedded/phase and RAW/phase captures passed
in five modes, with unique RAW/phase timestamp pairing. Libcamera now delivers
phase values to the IPA at 1080p. The experimental module has not replaced
the packaged module on disk.

PDAF now has independent QCOM CAMSS CSID/VFE metadata routing in each native
mode, short-run sequence/timestamp pairing with image frames, and center-grid
phase parsing in the IPA. Remaining work includes lens and scene calibration,
continuous reacquisition across distances, adverse-scene handling and
prolonged concurrent streaming.
The [IMX519 PDAF parser proposal](https://lists.libcamera.org/pipermail/libcamera-devel/2023-June/038275.html)
matches the captured row header and yields a lens-dependent signal. Test
near/far phase sign and confidence on the physical module. Two scene tests
confirmed the sign before phase-based lens moves were enabled in the private
libcamera. Distances were not measured.

## Build and hardware evidence

- Source: `radxa-pkg/libcamera` commit
  `de1e9bc095e23085e77533357d2582176de0a582`, the saved Radxa Debian
  patch series, `imx519.patch`, then `autofocus-simple.patch` (SHA-256
  `fd25bd5842f392c617ddaf63b143f570d019fe41c4ef25b5bf68a18aa3e4fbae`).
- Docker Ubuntu 24.04 arm64 build succeeded; `meson test --suite ipa` reported
  8 passed, 0 failed. The earlier CDAF runtime archive SHA-256 is
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
- The later PDAF runtime adds `color-native-size.patch` and
  `pdaf-simple.patch` to the same pinned source. Docker arm64 build and the
  eight IPA tests passed; archive SHA-256 is
  `bd10eaf6783fe0cf6108139ceb01eb7130de6814d571c22ec3530199a71be657`.
  A mixed-depth 1080p scene produced a phase spread of 36 and fell back to
  CDAF, ending Focused at raw code 1793. After the user arranged a fixed,
  lit contrasting target, Auto moved 2495 → 1895 → 1788 and reached median
  phase +1 without CDAF. The 1788 image scored 0.001844 normalized gradient
  energy in the central ROI, versus 0.000978 at 1488 and 0.001117 at 2088.
  Continuous moved 2495 → 1916 → 1809 → 1766 and reached phase −5 without
  fallback. Each libcamera run completed 360 color frames. The compact
  [evidence](../docs/evidence/2026-09-25-libcamera-pdaf.json) identifies the
  board artifacts and local photo. The final `pdaf5` runtime limits RAW
  timestamp storage to an active phase stream. It repeated phase focus at
  raw code 1781 (median phase 0) in 360 color frames, then captured three
  RAW-only frames successfully.

Run the checks using `cam.sh` and the `libcamera/af-*.yaml` scripts. For a
single AF photograph on the board run `bash snapshot-af.sh auto`. For a
read-only return to the previous runtime, set
`IMX519_RUNTIME=/home/radxa/camera-imx519/runtime/imx519-48c432913b9e.E1ywoR`
before `bash cam.sh ...`; `IMX519_LIBCAMERA=system` selects the apt build.

## Remaining qualification

The phase result uses a center 6×8 sensor grid and an eight-frame temporal
median, with CDAF fallback above a trimmed phase spread of 25. This threshold
and the provisional phase-to-lens slope need broader scene calibration.
Measured distance, low-light/flat-scene behavior, moving-subject reacquisition,
prolonged concurrent color/phase streaming and restart after a reboot still
need physical checks. The system libcamera and packaged CAMSS have not been
replaced by these private experimental builds.
