#!/usr/bin/env python3
"""Pair concurrent RAW and IMX519 PDAF buffers by V4L2 completion time."""

import argparse
import csv
import json
from pathlib import Path
from statistics import median


def frames(path: Path) -> list[tuple[int, int]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    return [(int(row["sequence"]),
             int(row["timestamp_sec"]) * 1_000_000 + int(row["timestamp_usec"]))
            for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    raw = frames(args.artifact / "raw-frames.csv")
    phase = frames(args.artifact / "phase/frames.csv")
    if len(raw) < 2 or len(phase) < 2:
        parser.error("At least two frames in each stream are required")
    pairs = [(p, min(raw, key=lambda r: abs(r[1] - p[1]))) for p in phase]
    offsets = [r[0] - p[0] for p, r in pairs]
    deltas = [p[1] - r[1] for p, r in pairs]
    raw_period = median(b[1] - a[1] for a, b in zip(raw, raw[1:]))
    if not (len({r[0] for _, r in pairs}) == len(phase) and
            len(set(offsets)) == 1 and
            max(map(abs, deltas)) < raw_period / 3):
        parser.error("RAW/phase pairing is ambiguous")
    result = {
        "artifact": args.artifact.name,
        "raw_frames": len(raw),
        "phase_frames": len(phase),
        "raw_sequences_contiguous": all(b[0] == a[0] + 1 for a, b in zip(raw, raw[1:])),
        "phase_sequences_contiguous": all(b[0] == a[0] + 1 for a, b in zip(phase, phase[1:])),
        "raw_minus_phase_sequence_offset": offsets[0],
        "phase_minus_raw_completion_timestamp_us": {
            "min": min(deltas), "median": median(deltas), "max": max(deltas),
        },
        "raw_frames_after_last_phase": sum(r[1] > phase[-1][1] for r in raw),
        "raw_median_period_us": raw_period,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
