#!/usr/bin/env python3
"""Validate short Q6A PDAF mode and concurrent RAW capture artifacts."""

import argparse
import csv
import json
import re
from pathlib import Path
from statistics import median


TARGET_FPS = {
    "4656x3496": 9,
    "3840x2160": 18,
    "2328x1748": 30,
    "1920x1080": 60,
    "1280x720": 80,
}


def read_csv(path):
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def mode_result(path):
    match = re.fullmatch(r"phase-mode-(\d+x\d+)-\d{8}T\d{6}Z", path.name)
    if not match:
        raise ValueError(f"Unexpected mode artifact path: {path}")
    mode = match.group(1)
    pairing = json.loads((path / "dual/pairing.json").read_text())
    embedded = json.loads((path / "dual/embedded/meta.json").read_text())
    phase = json.loads((path / "dual/phase/phase.json").read_text())
    rows = read_csv(path / "dual/phase/frames.csv")
    regions = [frame["qualified_regions"] for frame in phase["frames"]]
    phases = [frame["median_phase"] for frame in phase["frames"]]
    assert mode in TARGET_FPS
    assert mode in (path / "raw-setup.log").read_text()
    assert pairing["embedded_frames"] == pairing["phase_frames"] == 16
    assert pairing["paired_sequences"] == 16
    assert pairing["embedded_sequences_contiguous"]
    assert pairing["phase_sequences_contiguous"]
    assert pairing["phase_minus_embedded_timestamp_us"]["max_absolute"] < 200
    assert abs(pairing["embedded_fps"] / TARGET_FPS[mode] - 1) < 0.02
    assert embedded["sequences_contiguous"] and embedded["frames"] == 16
    assert len(phase["frames"]) == len(rows) == 16
    assert min(regions) > 0 and all(value is not None for value in phases)
    return {
        "mode": mode,
        "artifact": path.name,
        "target_fps": TARGET_FPS[mode],
        "measured_fps": pairing["embedded_fps"],
        "embedded_frames": pairing["embedded_frames"],
        "phase_frames": pairing["phase_frames"],
        "paired_sequences": pairing["paired_sequences"],
        "embedded_buffer_bytes": embedded["buffer_bytes"],
        "phase_buffer_bytes": int(rows[0]["bytesused"]),
        "phase_minus_embedded_timestamp_us": pairing["phase_minus_embedded_timestamp_us"],
        "qualified_regions_range": [min(regions), max(regions)],
        "median_phase": median(phases),
    }


def raw_phase_result(path):
    rows = read_csv(path / "phase/frames.csv")
    phase = json.loads((path / "phase/phase.json").read_text())
    raw_frames = (path / "raw.log").read_text().count("<")
    sequences = [int(row["sequence"]) for row in rows]
    assert raw_frames == 48
    assert len(rows) == len(phase["frames"]) == 24
    assert sequences == list(range(24))
    assert all(frame["qualified_regions"] > 0 for frame in phase["frames"])
    return {"artifact": path.name, "raw_frames": raw_frames,
            "phase_frames": len(rows), "phase_sequences_contiguous": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-sha256", required=True)
    parser.add_argument("--mode", action="append", type=Path, required=True)
    parser.add_argument("--raw-phase", action="append", type=Path, required=True)
    args = parser.parse_args()
    modes = sorted((mode_result(path) for path in args.mode),
                   key=lambda result: result["target_fps"])
    if len(modes) != len(TARGET_FPS) or {row["mode"] for row in modes} != set(TARGET_FPS):
        parser.error("Exactly one artifact for each native mode is required")
    raw_phase = [raw_phase_result(path) for path in args.raw_phase]
    if len(raw_phase) < 2:
        parser.error("Two concurrent RAW/PDAF trials are required")
    print(json.dumps({"module_sha256": args.module_sha256,
                      "modes": modes, "raw_phase_trials": raw_phase}, indent=2))


if __name__ == "__main__":
    main()
