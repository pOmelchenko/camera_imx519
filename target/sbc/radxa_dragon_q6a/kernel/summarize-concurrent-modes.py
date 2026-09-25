#!/usr/bin/env python3
"""Validate simultaneous RAW and PDAF capture in all Q6A IMX519 modes."""

import argparse
import json
import re
from pathlib import Path


TARGET_FPS = {
    "4656x3496": 9,
    "3840x2160": 18,
    "2328x1748": 30,
    "1920x1080": 60,
    "1280x720": 80,
}


def summarize(path):
    match = re.fullmatch(r"raw-phase-(\d+x\d+)-\d{8}T\d{6}Z", path.name)
    if not match or match.group(1) not in TARGET_FPS:
        raise ValueError(f"Unexpected artifact path: {path}")
    mode = match.group(1)
    fps = TARGET_FPS[mode]
    pairing = json.loads((path / "pairing.json").read_text())
    phase = json.loads((path / "phase/phase.json").read_text())
    regions = [frame["qualified_regions"] for frame in phase["frames"]]
    assert pairing["raw_frames"] == fps * 4
    assert pairing["phase_frames"] == fps * 2 == len(regions)
    assert pairing["raw_sequences_contiguous"]
    assert pairing["phase_sequences_contiguous"]
    assert pairing["raw_frames_after_last_phase"] > 0
    assert pairing["phase_minus_raw_completion_timestamp_us"]["max"] < pairing["raw_median_period_us"] / 3
    assert abs(1_000_000 / pairing["raw_median_period_us"] / fps - 1) < 0.02
    assert min(regions) > 0
    return {
        "mode": mode,
        "artifact": path.name,
        "target_fps": fps,
        "raw_frames": pairing["raw_frames"],
        "phase_frames": pairing["phase_frames"],
        "raw_median_period_us": pairing["raw_median_period_us"],
        "raw_minus_phase_sequence_offset": pairing["raw_minus_phase_sequence_offset"],
        "phase_minus_raw_completion_timestamp_us": pairing["phase_minus_raw_completion_timestamp_us"],
        "raw_frames_after_last_phase": pairing["raw_frames_after_last_phase"],
        "qualified_regions_range": [min(regions), max(regions)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-sha256", required=True)
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()
    modes = sorted((summarize(path) for path in args.artifacts),
                   key=lambda item: item["target_fps"])
    if len(modes) != len(TARGET_FPS) or {item["mode"] for item in modes} != set(TARGET_FPS):
        parser.error("Exactly one artifact for each native mode is required")
    print(json.dumps({"module_sha256": args.module_sha256, "modes": modes}, indent=2))


if __name__ == "__main__":
    main()
