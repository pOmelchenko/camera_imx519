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
  current media nodes, links CSIPHY3 to CSID0 and CSID0 RDI1 to VFE0 RDI1,
  copies the current sensor RAW format to the upstream CAMSS sink pads,
  configures `SENSOR_DATA/17460x1` and selects `MET8` on the capture node. The
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
  The corrected module was subsequently tested after a power cycle; see below.
  Do not claim that embedded data or PDAF is available until a real buffer is
  captured and its contents are validated.
- The owner power-cycled Q6A to recover the wedged task. After that action,
  SSH to the previous address `192.168.1.67` timed out from both the owner and
  workstation; an ICMP check also timed out. The board's boot and camera
  state was temporarily unavailable. SSH later returned with boot ID
  `9c3d826a-4763-43a3-9af6-2f88262327dd`, stock CAMSS loaded and no
  wedged process. The experimental module had only been loaded in memory; no
  CAMSS module was installed on disk.
- The corrected experimental module was loaded in memory. A zero-frame probe
  passed `REQBUFS` and all four `QUERYBUF` calls with 17,472-byte buffers,
  exited successfully and left no process behind. This confirms the prior
  `__fill_v4l2_buffer` fault is fixed in this probe.
- The first `STREAMON` returned `ENOLINK` because the CSIPHY3 → CSID0 link had
  not been enabled after module reload. That failed start left VFE0 RDI1
  running: `camss-video.c` did not stop subdevices already started when a later
  one failed. A later attempt logged `call_s_stream` for an already started
  subdevice. This was a kernel warning, **not** an oops. An earlier warning at
  05:31:58 was from the DisplayPort clock driver and unrelated to CAMSS.
- With the link enabled, `STREAMON` succeeded but repeated four-frame MET8
  samples timed out after five seconds with zero completed buffers. VFE0 IRQ
  count rose by 91 during a roughly two-second metadata stream, without a
  completed metadata buffer. After a short libcamera RAW control, three
  1920×1080 frames arrived with consecutive sequence numbers. The same MET8
  timeout persisted after matching the upstream RAW format to the current
  1920×1080 sensor mode. CAMSS use count returned to zero after each attempt.
- A new experimental CAMSS build fixes partial-start unwind and ensures stream
  stop always releases the media pipeline and queued buffers. It compiled on
  Q6A as SHA-256 `7ba67049f961c50400fb7d9396bd2e8c790f1feed7e8ff292fa2cc4ad202697b`.
  After loading it, an intentional CSIPHY3 → CSID0 disconnection caused the
  expected `ENOLINK`; the capture process exited and CAMSS reference count
  returned to zero. A normal MET8 run still timed out without a buffer.
- The pinned VFE 17x ISR gates every write-master completion on IRQ_STATUS_0
  bit 9 (the WM1 ping-pong bit). A September 2026
  [upstream fix proposal](https://lkml.iu.edu/2609.1/18995.html) identifies
  this as a lost-buffer bug and dispatches directly from the per-WM BUS IRQ
  status. The same correction is staged as SHA-256
  `b1a4eb5bc64fa10c45e97d1a9730b059ce6c85d34c2cb0717ce88e51de3b6472`.
  After loading it, both 1920×1080 and 4656×3496 standalone MET8 captures
  still timed out with zero buffers. The ISR fix alone is insufficient.
- A read-only MMIO sample during an active full-resolution MET8 capture showed
  CSID0 RDI1 `CFG0=0x8812f007` (VC0, DT `0x12`, enabled), `CTRL=1`; VFE0
  WM0 `CFG=3` (enabled) and `FRAME_INC=0x4440` (17,472 bytes). RDI0 and WM1
  were disabled. The capture still timed out and left no CAMSS reference.
  [The register reader](../kernel/read-camss-registers.py) derives the physical
  register bases from the board device tree and opens `/dev/mem` read-only.
  A repeat sample during the same stream found `rx_total_packets` increasing
  from `0x4bfa` to `0xcf65` in about one second, zero RX CRC errors, and
  changing RDI1 SOF/EOF timestamps. This is evidence that CSI packets and
  frame markers reach CSID0. The RDI1 ping/pong byte counters both read
  `0x2d78` (11,640), while the sensor pad advertises 17,460 bytes and MET8
  allocates 17,472. The counter semantics and actual payload length have not
  been independently confirmed. VFE0 interrupts increased by 91 during the
  approximately nine-second MET8 run, but no buffer completed. The next
  experiment compares VFE register state during a working RAW stream and the
  failing metadata stream before changing DMA configuration. Additional CSID
  offsets are taken from Qualcomm's
  [CSID 175 register layout](https://android.googlesource.com/kernel/msm/+/04749e7fec2a8a5784a984d09f03fd0f2715fd1b/drivers/media/platform/msm/ais/cam_isp/isp_hw_mgr/isp_hw/ife_csid_hw/cam_ife_csid175.h).
- A control RAW stream at 4656×3496 delivered frames 69–75 at 9 fps. Its
  register sample showed CSID0 RDI0 enabled, VFE0 WM0 enabled, and VFE0
  `wm0_status0` changing from `0xf0000000` to `0xf6000000`. The MET8 stream
  used CSID0 RDI1 but also VFE0 WM0. The pinned VFE 17x driver selects the
  first free WM, whereas gen2 VFE requires RDI n → WM n. An
  [upstream VFE 17x fix](https://lkml.iu.edu/2609.1/19112.html) identifies
  this precise mapping error. The experiment now uses `vfe_get_output_v2()`
  to select WM1 for RDI1. The resulting module compiled on Q6A as SHA-256
  `fe001d5623587a313a4bc0be0474ba8ef7869c21ebd977e1afe247e33ec765db`.
  The owner loaded it temporarily in memory. The first four-frame MET8
  capture completed with sequences 0–3 and 17,472 reported bytes per frame,
  at approximately 9 fps. This establishes a functioning metadata DMA path.
- The captured 4656×3496 buffers contain nonzero data only in the first two
  5,824-byte aligned rows. The third row expected by the
  [Raspberry Pi IMX519 PDAF parser](https://lists.libcamera.org/pipermail/libcamera-devel/2023-June/038275.html)
  is entirely zero in all four samples. Only byte 7 changes between frames,
  increasing from 1 to 4. The same experiment at 1920×1080 completed four
  MET8 frames at approximately 60 fps; only its first two 2,400-byte rows
  are nonzero, and again only byte 7 changes. The two mode summaries are
  [full resolution](../docs/evidence/2026-09-25-meta-wm1.json) and
  [1080p](../docs/evidence/2026-09-25-meta-wm1-1920.json), generated by
  [analyze-meta.py](../kernel/analyze-meta.py); raw samples are under ignored
  `var/q6a-imx519/meta-wm1-*`. The buffer's reported `bytesused` equals the
  allocated length, so it does not establish how many bytes the sensor sent.
  The actual third phase row is not observed in either mode. The AK7375 still
  uses CDAF only.
- A register read during an active RAW stream (`0x0100=1`) confirmed the
  installed sensor driver's PDAF settings on the physical camera:
  `0x3e20=1`, `0x3e37=1`, `0x3e3b=0`, `0x38a3=0`. The installed DKMS source
  matches the saved Arducam-derived `driver/imx519.c` by SHA-256.
- A later 16-frame MET8 capture completed while CSID0's unmapped long-packet
  header reported VC0/DT `0x36`, WC 5,820 bytes. RDI1 was configured for
  VC0/DT `0x12` and its byte counters showed 11,640 bytes: exactly two
  5,820-byte rows. CSI-2 DT `0x36` is [user-defined 8-bit data](https://community.infineon.com/t5/%E3%83%8A%E3%83%AC%E3%83%83%E3%82%B8%E3%83%99%E3%83%BC%E3%82%B9%E3%82%A2%E3%83%BC%E3%83%86%E3%82%A3%E3%82%AF%E3%83%AB-KBA/CX3%E3%81%A7%E3%82%B5%E3%83%9D%E3%83%BC%E3%83%88%E3%81%95%E3%82%8C%E3%82%8BMIPI-Data-Type-ID-KBA232765/ta-p/393059).
  Its length matches one full-width PDAF row and Raspberry Pi's libcamera
  [discussion](https://patchwork.libcamera.org/patch/18758/) says PDAF can use
  a separate packet ID. This is a strong candidate for the missing phase
  row, not yet proof of its payload. A diagnostic-only `probe_phase_dt36`
  module parameter now switches RDI1's filter from `0x12` to `0x36`; default
  remains `0x12`. The wrapper [probe-phase-dt36.sh](../kernel/probe-phase-dt36.sh)
  restores the default after a bounded capture. The module compiled on Q6A
  as SHA-256 `a4b4f4d9a4df9a69a98936025bcb1c7d15b16a402bc21cf9ca68c7975bdcdc65`.
- The owner loaded that module and captured 16 contiguous VC0/DT `0x36`
  frames. RDI1 byte counters showed 5,820 bytes; the unmapped long header
  switched to DT `0x12`. Each DMA buffer has a nonzero first row and zero
  remainder. The PDAF header `00 15` passes the published parser's check.
  [analyze-phase.py](../kernel/analyze-phase.py) decodes the proposed 12×16
  grid: with confidence threshold 16 it finds 35–39 qualified regions per
  frame, median phases −127 to −121. The compact
  [16-frame summary](../docs/evidence/2026-09-25-phase-dt36.json) is checked
  in; raw frames are in ignored `var/q6a-imx519/`. This confirms a live phase
  payload, but the sign, calibration and autofocus response remain untested.
- With a fixed lit scene, [probe-phase-focus.sh](../kernel/probe-phase-focus.sh)
  held AK7375 at 2047 and 2496 for eight phase frames each. All sequences
  were contiguous. Frame-median phase moved from approximately −17 (75–77
  confident regions) to +44 (60–64 confident regions); the median of
  confidence-weighted phase means moved from −25.5 to +42.2. The saved
  [2047](../docs/evidence/2026-09-25-phase-focus-2047.json) and
  [2496](../docs/evidence/2026-09-25-phase-focus-2496.json) summaries show
  the individual frames. This demonstrates a lens-dependent phase signal.
  It does not establish the focus-distance mapping or a stable closed loop.
- The experimental Gen2 CSID now maps RDI1 to VC0/DT `0x12` and RDI2 to
  VC0/DT `0x36`, with VFE0 WM1/WM2 and `/dev/video3`/`/dev/video4` MET8
  nodes. Sequential captures delivered 16 phase and eight embedded frames.
  A simultaneous 24-frame embedded/phase run produced matching sequences
  0–23 at 9.002 fps, with phase timestamps 34–62 µs after embedded timestamps
  (median 48 µs). The [pairing summary](../docs/evidence/2026-09-25-dual-meta-pairing.json)
  is generated by [pair-meta.py](../kernel/pair-meta.py).
- A first concurrent RAW+phase run delivered 24 phase frames but RAW stalled
  after about 29 and timed out; RAW alone completed 16 frames. The pinned
  CAMSS unconditionally reset all of VFE0 when any RDI stopped. Resetting
  only when the last RDI stops was insufficient: a second run with module
  `b051e636b78cd10cb91cb49ef4336b112972b107637cb7278f5eb74efb10e3c0`
  again timed out. The kernel then logged a write-master completion for an
  unmapped index and IOMMU faults. The phase DMA buffer was being returned
  before the VFE acknowledged the WM disable. The driver now requests an RDI
  register update after disabling that WM and waits for its acknowledgement
  before vb2 can unmap buffers. Module SHA-256
  `338ff57678402fbde17b9c4ea1b4c7a16d732f51c8342fa1241b06bb62ba7dc0`
  completed two [RAW+phase trials](../docs/evidence/2026-09-25-pdaf-five-modes.json):
  each produced 48 RAW frames and 24 contiguous phase frames, with both
  processes exiting successfully. No new CAMSS/IOMMU error appeared in the
  accessible kernel journal after these runs.
- The metadata setup now derives payload length from the selected RAW10 width:
  two DT `0x12` rows and one separate DT `0x36` row. Short simultaneous
  embedded/phase captures succeeded in all five native sensor modes. Each
  yielded 16 paired contiguous frames; measured embedded rates were 9.003,
  17.999, 29.996, 59.941 and 79.997 fps. Maximum absolute phase-to-embedded
  timestamp difference was 64 µs, and each phase frame contained qualified
  regions. [Compact evidence](../docs/evidence/2026-09-25-pdaf-five-modes.json)
  is generated by [summarize-pdaf-gates.py](../kernel/summarize-pdaf-gates.py);
  raw diagnostic buffers remain outside Git under `var/q6a-imx519/`.
- A RAW timestamp recorder then captured concurrent RAW and phase buffers in
  every native mode for approximately four and two seconds respectively.
  RAW counts were 36, 72, 120, 240 and 320; phase counts were 18, 36, 60,
  120 and 160. All sequences were contiguous, nearest-timestamp pairing was
  unique with a constant sequence offset in each run, and RAW continued after
  phase stopped. The largest phase-minus-RAW buffer completion difference was
  2.418 ms at 9 fps; the other modes were lower. These timestamps mark DMA
  completion, not exposure start. [Evidence](../docs/evidence/2026-09-25-concurrent-raw-phase-five-modes.json)
  is generated by [summarize-concurrent-modes.py](../kernel/summarize-concurrent-modes.py).
- Fixed-scene phase sweeps then bracketed zero at two user-arranged distances.
  The first scene refined to AK7375 raw code 1947 (median central phase −2),
  and the later, nominally farther scene to 1646 (+0.25). Both codes gave the
  best selected-region sharpness among their ±300-code color controls. Actual
  distances were not measured and the regions include mixed depths. See
  [near](../docs/evidence/2026-09-25-phase-focus-near.json) and
  [far](../docs/evidence/2026-09-25-phase-focus-far.json) evidence.
- The board-only [one-shot controller](../snapshot-pdaf.py) then measured a
  changed scene at codes 2047, 2133 and 2104. Central phase converged from
  −12 through +6 to −0.25, and a focused color image was saved. Its selected
  code had better central sharpness than controls at 1804 and 2404. The
  [compact record](../docs/evidence/2026-09-25-snapshot-pdaf.json) retains
  samples and scores; complete artifacts are ignored under `var/`. This
  controller drives the lens between separate phase captures and uses the
  existing CDAF snapshot as fallback. It is not yet libcamera's in-stream AF.
- A later private libcamera build now streams RAW and VC0/DT `0x36` phase
  metadata together at 1080p, pairs their timestamps, and feeds the simple
  IPA. An eight-frame median drove AK7375 from 2495 through 1895 to 1788,
  where central phase was +1. A second Continuous run converged at 1766 with
  phase −5. Manual color frames at raw codes 1488, 1788 and 2088 had their
  highest selected-region sharpness at 1788. An earlier mixed-depth scene
  produced unstable phase and exercised CDAF fallback. See
  [libcamera PDAF evidence](../docs/evidence/2026-09-25-libcamera-pdaf.json).
  These are short physical tests of one lit scene, not prolonged qualification
  or proof of moving-subject reacquisition.

## Remaining gates

1. Extend the successful short runs to concurrent RAW, embedded and phase
   streaming, repeated start/stop and long runs in all five modes. RAW/phase
   pairing is established; all three simultaneous streams remain untested.
2. Calibrate the phase grid, focus distance and confidence across more measured
   scenes. The private libcamera IPA now moves the lens from phase and falls
   back to CDAF for missing or unstable phase; validate those thresholds on
   flat, dark and mixed-depth scenes.
3. Run simultaneous color and metadata capture for each mode and five-minute
   per-mode qualification: target FPS, zero sequence gaps/errors, stable AF
   state, and near/far transitions. Archive compact summaries; leave raw
   captures outside Git.
