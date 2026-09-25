#!/usr/bin/env python3
"""Estimate a zero-phase AK7375 code from a fixed-scene focus sweep."""

import argparse
import json
from pathlib import Path
from statistics import median


def point(path):
    code = int(path.name.removeprefix("focus-"))
    frames = json.loads((path / "phase-center.json").read_text())["frames"]
    qualified = [frame["qualified_regions"] for frame in frames]
    phases = [frame["median_phase"] for frame in frames]
    valid_phases = [value for value in phases if value is not None]
    usable = len(frames) >= 4 and min(qualified) >= 8 and len(valid_phases) == len(frames)
    return {"code": code, "median_phase": median(valid_phases) if valid_phases else None,
            "qualified_regions_min": min(qualified) if qualified else 0,
            "phase_range": [min(valid_phases), max(valid_phases)] if valid_phases else None,
            "usable": usable}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sweep", type=Path)
    args = parser.parse_args()
    samples = sorted((point(path) for path in args.sweep.glob("focus-*")),
                     key=lambda item: item["code"])
    usable_samples = [sample for sample in samples if sample["usable"]]
    if len(usable_samples) < 2:
        parser.error("At least two focus positions need qualified central PDAF data")
    brackets = [(a, b) for a, b in zip(usable_samples, usable_samples[1:])
                if a["median_phase"] * b["median_phase"] <= 0 and
                abs(b["median_phase"] - a["median_phase"]) >= 10]
    if brackets:
        a, b = min(brackets, key=lambda pair: pair[1]["code"] - pair[0]["code"])
        candidate = round(a["code"] - a["median_phase"] *
                          (b["code"] - a["code"]) /
                          (b["median_phase"] - a["median_phase"]))
        if not a["code"] <= candidate <= b["code"]:
            raise ValueError("Interpolation escaped measured bracket")
    else:
        candidate = None
    print(json.dumps({"samples": samples,
                      "status": "bracketed" if candidate is not None else "no_bracket",
                      "candidate_raw_code": candidate}, indent=2))


if __name__ == "__main__":
    main()
