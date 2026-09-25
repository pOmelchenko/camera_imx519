# IMX519 PDAF bring-up on Dragon Q6A

Updated 2026-09-25 (Europe/Moscow). Target: Ubuntu 24.04.4,
`7.0.11-6-qcom`, `qcom,sc7280-camss`. This is experimental work, not a
qualification of phase autofocus.

## Reproducible source and module

- CAMSS source: `radxa/kernel` commit
  `657c0f722940cd9d3b51abfa7383655ec7d2c795`, pinned by
  `radxa-pkg/linux-qcom` tag `7.0.11-6`.
- [CAMSS patch](../kernel/camss-pdaf.patch) adds CSI embedded-data DT `0x12`
  on RDI1 while RAW10 remains on VC0/RDI0. It provides the `SENSOR_DATA`
  media bus format through CSID and VFE and `MET8` capture through VFE RDI.
- [Build/stage recipe](../kernel/build-and-stage.sh) checks the source commit,
  applies the patch to a copy, builds against the installed headers on Q6A,
  and leaves `qcom-camss.ko` in the user's build directory. It does not
  replace the packaged module. The installed header package and the module
  agree on vermagic. The compiler differs from the compiler used for the
  distro kernel (GCC 13.3 vs 12.2); no compile errors were reported.
- [Activation](../kernel/activate-pdaf.sh) swaps the module in memory after
  `sudo -v`; [rollback](../kernel/rollback-pdaf.sh) reloads the packaged module.
  A reboot also discards the in-memory module. The first activation failed
  because `modprobe -r` unloaded `videobuf2-dma-sg` and `insmod` cannot load
  dependencies; the activation script now explicitly reloads them.
- After activation, [prepare-meta.sh](../kernel/prepare-meta.sh) discovers the
  current media nodes, links CSID0 RDI1 to VFE0 RDI1, configures
  `SENSOR_DATA/17460x1` and selects `MET8` on the capture node. The
  [capture utility](../kernel/capture-meta.c) accepts count `0` for a
  `REQBUFS`/`QUERYBUF` probe without mapping or starting the stream.

## Results so far

- Private libcamera with [native color mode patch](../libcamera/color-native-size.patch)
  built in Ubuntu 24.04 arm64 and passed 8/8 IPA tests. After deployment,
  short 60-frame `XRGB8888` captures selected the matching sensor mode for all
  five requested sizes, with last-frame readings near 9, 18, 30, 60 and
  80 fps. This is a mode-selection and short throughput result, not a
  five-minute qualification or a PDAF result.
- An illuminated 1080p one-shot contrast AF capture returned
  `AfStateFocused` and was copied to `var/` on the workstation. This still
  uses CDAF.
- The experimental CAMSS module loaded successfully in memory. The media
  graph accepted CSID pad 2 and VFE0 RDI1 pad 0 as
  `MEDIA_BUS_FMT_SENSOR_DATA/17460x1`. `/dev/video3` enumerated
  `V4L2_META_FMT_GENERIC_8` (`MET8`), and `S_FMT_META_CAPTURE` returned a
  17,472-byte aligned buffer size.
- The first 16-frame metadata attempt produced no sample file. The privileged
  kernel stack showed a page fault in `__fill_v4l2_buffer` during
  `VIDIOC_QUERYBUF`. The subsequent task exit blocked in `vb2_fop_release`,
  leaving the task in uninterruptible sleep and holding one CAMSS module
  reference. The pinned videobuf2 source computes `q->is_multiplanar` during
  queue initialization. Our first patch changed `q->type` from VIDEO_CAPTURE_MPLANE
  to META_CAPTURE but left that cached flag set. `__fill_v4l2_buffer` then
  treated the single-planar metadata buffer as multi-planar and dereferenced
  the absent plane array. The patch now changes the cached flag together with
  the queue type using `vb2_queue_change_type`; this correction rebuilt as
  SHA-256 `a5aca0f53a3168d45da967ea9b5c3b602530779704239bed0629404765219bfa`.
  The corrected module has **not yet passed** `VIDIOC_QUERYBUF` or streaming.
  A reboot is required to clear the hung process and restore the stock module
  before retesting. Do not claim that embedded data or PDAF is available until
  a real buffer is captured and its contents are validated.
- The owner power-cycled Q6A to recover the wedged task. After that action,
  SSH to the previous address `192.168.1.67` timed out from both the owner and
  workstation; an ICMP check also timed out. The board's boot and camera
  state are therefore unverified after the power cycle. The experimental
  module had only been loaded in memory; no CAMSS module was installed on disk.

## Remaining gates

1. Restore Q6A access and verify boot ID, stock module, and camera topology.
   Then load the corrected module in memory and confirm that `VIDIOC_QUERYBUF`
   and stream shutdown work without faults.
2. Capture actual CSI metadata per sensor mode. Confirm VC, DT, payload
   length, sequence/timestamp pairing, and whether phase samples are present.
3. Parse and calibrate the phase grid from observed bytes. Determine near/far
   sign and confidence at multiple distances on this lens; only then feed a
   phase move to the private libcamera IPA, retaining CDAF fallback.
4. Run simultaneous color and metadata capture for each mode and five-minute
   per-mode qualification: target FPS, zero sequence gaps/errors, stable AF
   state, and near/far transitions. Archive compact summaries; leave raw
   captures outside Git.
