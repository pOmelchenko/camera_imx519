#!/usr/bin/env python3
"""Check sequence and timestamp pairing of two CAMSS capture-meta streams."""

import argparse
import csv
import json
from pathlib import Path
from statistics import median


def read_frames(path: Path) -> list[tuple[int, int]]:
    with (path / "frames.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    return [
        (int(row["sequence"]),
         int(row["timestamp_sec"]) * 1_000_000 + int(row["timestamp_usec"]))
        for row in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("embedded", type=Path)
    parser.add_argument("phase", type=Path)
    args = parser.parse_args()
    embedded = read_frames(args.embedded)
    phase = read_frames(args.phase)
    if len(embedded) < 2 or len(phase) < 2:
        parser.error("At least two frames in each stream are required")
    embedded_map = dict(embedded)
    phase_map = dict(phase)
    if len(embedded_map) != len(embedded) or len(phase_map) != len(phase):
        parser.error("Duplicate sequence number")
    common = sorted(embedded_map.keys() & phase_map.keys())
    deltas = [phase_map[sequence] - embedded_map[sequence] for sequence in common]
    span = embedded[-1][1] - embedded[0][1]
    summary = {
        "embedded_directory": args.embedded.name,
        "phase_directory": args.phase.name,
        "embedded_frames": len(embedded),
        "phase_frames": len(phase),
        "embedded_sequences_contiguous": all(b[0] == a[0] + 1 for a, b in zip(embedded, embedded[1:])),
        "phase_sequences_contiguous": all(b[0] == a[0] + 1 for a, b in zip(phase, phase[1:])),
        "paired_sequences": len(common),
        "first_paired_sequence": common[0] if common else None,
        "last_paired_sequence": common[-1] if common else None,
        "phase_minus_embedded_timestamp_us": {
            "min": min(deltas) if deltas else None,
            "median": median(deltas) if deltas else None,
            "max": max(deltas) if deltas else None,
            "max_absolute": max(map(abs, deltas)) if deltas else None,
        },
        "embedded_fps": round((len(embedded) - 1) * 1_000_000 / span, 3) if span > 0 else None,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
