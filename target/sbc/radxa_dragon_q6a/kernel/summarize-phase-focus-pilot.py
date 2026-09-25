#!/usr/bin/env python3
"""Summarize one physical phase-zero and optical sharpness check."""

import argparse
import json
from pathlib import Path
from statistics import median


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sweep", type=Path)
    parser.add_argument("sharpness", type=Path)
    parser.add_argument("--scene-note", required=True)
    parser.add_argument("--score-file", default="score-object.json")
    args = parser.parse_args()
    estimate = json.loads((args.sweep / "estimate.json").read_text())
    assert estimate["status"] == "bracketed"
    candidates = []
    for path in sorted(args.sweep.glob("candidate-*")):
        frames = json.loads((path / "phase-center.json").read_text())["frames"]
        phases = [frame["median_phase"] for frame in frames]
        regions = [frame["qualified_regions"] for frame in frames]
        assert len(frames) >= 8 and all(value is not None for value in phases)
        candidates.append({"raw_code": int(path.name.removeprefix("candidate-")),
                           "frames": len(frames),
                           "median_central_phase": median(phases),
                           "phase_range": [min(phases), max(phases)],
                           "qualified_regions_range": [min(regions), max(regions)]})
    score = json.loads((args.sharpness / args.score_file).read_text())
    optical = [{"raw_code": int(Path(row["file"]).stem.removeprefix("focus-")),
                "normalized_energy": row["normalized_energy"]}
               for row in score["results"]]
    assert len(candidates) >= 2 and len(optical) == 3
    print(json.dumps({
        "sweep_artifact": args.sweep.name,
        "sharpness_artifact": args.sharpness.name,
        "scene_note": args.scene_note,
        "initial_estimate": estimate,
        "verification": candidates,
        "optical_roi": score["roi"],
        "optical_scores": optical,
        "optical_best_raw_code": max(optical, key=lambda item: item["normalized_energy"])["raw_code"],
    }, indent=2))


if __name__ == "__main__":
    main()
