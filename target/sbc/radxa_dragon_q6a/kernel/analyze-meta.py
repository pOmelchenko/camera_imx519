#!/usr/bin/env python3
"""Summarize captured MET8 bytes without assuming that PDAF is present."""

import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--image-width", type=int, default=4656)
    parser.add_argument("--bit-depth", type=int, default=10)
    args = parser.parse_args()
    if args.image_width <= 0 or args.bit_depth <= 0:
        parser.error("Image width and bit depth must be positive")

    paths = sorted(args.directory.glob("frame-*.bin"))
    if not paths:
        parser.error("No frame-*.bin files found")
    frames = [path.read_bytes() for path in paths]
    lengths = {len(frame) for frame in frames}
    if len(lengths) != 1:
        parser.error("Captured frames have different lengths")

    payload_width = (args.image_width * args.bit_depth + 7) // 8
    line_stride = (payload_width + 15) & ~15
    rows = min(3, len(frames[0]) // line_stride)
    manifest = args.directory / "frames.csv"
    sequences = []
    if manifest.exists():
        with manifest.open(newline="") as source:
            sequences = [int(row["sequence"]) for row in csv.DictReader(source)]

    summary = {
        "frames": len(frames),
        "buffer_bytes": len(frames[0]),
        "image_width": args.image_width,
        "bit_depth": args.bit_depth,
        "payload_bytes_per_line": payload_width,
        "aligned_line_stride": line_stride,
        "sequences": sequences,
        "sequences_contiguous": len(sequences) == len(frames) and all(
            next_seq == seq + 1 for seq, next_seq in zip(sequences, sequences[1:])
        ),
        "last_nonzero_offset": [
            next((i for i in range(len(frame) - 1, -1, -1) if frame[i]), -1)
            for frame in frames
        ],
        "nonzero_bytes_per_row": [
            [sum(value != 0 for value in frame[i * line_stride:(i + 1) * line_stride])
             for i in range(rows)]
            for frame in frames
        ],
        "changed_bytes_between_frames_per_row": [
            [sum(a != b for a, b in zip(
                frames[n][i * line_stride:(i + 1) * line_stride],
                frames[n + 1][i * line_stride:(i + 1) * line_stride]))
             for i in range(rows)]
            for n in range(len(frames) - 1)
        ],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
