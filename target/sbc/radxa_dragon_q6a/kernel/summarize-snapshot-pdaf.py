#!/usr/bin/env python3
"""Retain compact evidence from an automatic phase-guided photo."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("autofocus", type=Path)
    parser.add_argument("sharpness", type=Path)
    args = parser.parse_args()
    result = json.loads((args.autofocus / "result.json").read_text())
    score = json.loads((args.sharpness / "score.json").read_text())
    assert result["method"] == "PDAF" and result["phase_error"] is None
    assert len(result["samples"]) >= 2
    assert abs(result["samples"][-1]["phase"]) <= 5
    optical = [{"raw_code": int(Path(row["file"]).stem.removeprefix("focus-")),
                "normalized_energy": row["normalized_energy"]}
               for row in score["results"]]
    assert len(optical) == 3
    print(json.dumps({
        "autofocus_artifact": args.autofocus.name,
        "sharpness_artifact": args.sharpness.name,
        "method": result["method"],
        "selected_raw_code": result["selected_raw_code"],
        "phase_samples": result["samples"],
        "optical_roi": score["roi"],
        "optical_scores": optical,
        "optical_best_raw_code": max(optical, key=lambda item: item["normalized_energy"])["raw_code"],
        "scene_note": "Scene changed after the earlier far sweep; actual distance unmeasured",
    }, indent=2))


if __name__ == "__main__":
    main()
