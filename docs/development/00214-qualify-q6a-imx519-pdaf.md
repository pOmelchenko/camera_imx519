---
type: backlog-task
status: deferred
number: 00214
epic: Camera
priority: P2
updated: 2026-10-12
---

# 00214 Qualify Q6A IMX519 PDAF And Recovery

## Goal

Turn the short, physically verified IMX519 PDAF runs on Radxa Dragon Q6A into
repeatable autofocus, concurrent-stream and recovery evidence. Decide from
those results whether the experimental CAMSS and private libcamera stack is
ready for a separately reviewed persistent installation.

## Current State And Activation

The experimental CAMSS module exposes VC0/DT `0x12` embedded data and VC0/DT
`0x36` phase data. Short concurrent RAW/phase runs passed in all five native
sensor modes. Private libcamera `pdaf5` reached phase focus in Auto and
Continuous on one lit, stationary scene; an earlier mixed-depth scene fell
back to contrast AF. Manual sharpness controls favored the phase-selected
lens code. The CAMSS module is loaded only in memory; a reboot restores the
packaged module. Neither moving-subject reacquisition nor prolonged PDAF
streaming has been qualified.

Activate when the physical Q6A/IMX519 fixture is available for supervised
tests, the source/build hashes are pinned, and the user can arrange the
required scenes. Ask the user before any illumination-dependent test and wait
for confirmation that the light and scene are ready.

## Scope

- Record the exact board, kernel, sensor/lens variant, CAMSS module, private
  libcamera build, tuning and test commands before each run. Keep the package
  under `target/sbc/radxa_dragon_q6a/`; keep large captures in ignored `var/`.
- Measure Continuous AF through repeated near → far → near transitions on
  stationary targets at measured distances. Record lens codes, phase quality,
  focus-state transitions and time to settle. Compare selected-region image
  sharpness with manual positions at each distance; a `Focused` flag alone is
  insufficient.
- Exercise low-confidence cases: dark, flat and mixed-depth scenes, phase-node
  absence, start failure and lost phase buffers. Verify bounded fallback to
  contrast AF or an explicit failure state, with no false phase-success claim.
  Perform dark/light scene changes only after the user confirms readiness.
- Run concurrent RAW, embedded DT `0x12` and phase DT `0x36` capture, including
  one stream stopping before the others. Repeat stop/start cycles and check
  buffer ownership, unique timestamp pairing and absence of CAMSS/IOMMU faults
  or blocked capture processes.
- Run color plus phase capture for at least five minutes in each of the five
  native sensor modes. Record actual frame rates, sequences, metadata pairing,
  AF state, bounded memory/queues and kernel errors. Use counter-only or
  bounded output where full RAW storage is unnecessary.
- Verify operation after a clean reboot, temporary experimental-module load
  and rollback to the packaged CAMSS. Document recovery from an interrupted
  capture. A persistent module or package installation is a separate decision
  after these gates pass, with saved stock artifacts and a tested rollback.

## Acceptance

- A reproducible runbook and compact evidence identify every tested mode,
  scene, version and acceptance result; failed or untested rows remain explicit.
- Near/far transitions show phase-driven lens movement toward a measured
  optical sharpness maximum within a recorded settling bound, without repeated
  oscillation or a stuck `Scanning` state.
- Low-confidence cases have a measured, bounded fallback or failure result;
  light changes follow user confirmation.
- Each five-minute mode run completes at its configured, recorded rate with
  explainable sequence accounting and phase/image pairing. No unexplained
  buffer loss, memory growth, kernel fault or blocked teardown is accepted.
- Stop/start, reboot and rollback checks leave the camera usable. Persistent
  deployment is recommended only with evidence and a concrete recovery path;
  this task does not silently replace system packages or the boot module.

## Sources

- [Q6A IMX519 package and commands](../../target/sbc/radxa_dragon_q6a/README.md).
- [PDAF bring-up and remaining gates](../../target/sbc/radxa_dragon_q6a/research/pdaf-bringup.md).
- [Short libcamera PDAF evidence](../../target/sbc/radxa_dragon_q6a/docs/evidence/2026-09-25-libcamera-pdaf.json).
