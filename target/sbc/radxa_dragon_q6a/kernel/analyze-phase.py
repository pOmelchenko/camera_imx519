#!/usr/bin/env python3
"""Summarize a separate IMX519 10-bit PDAF packet captured as MET8.

The 12x16 grid layout follows Arducam's proposed IMX519 libcamera helper:
https://patchwork.libcamera.org/patch/18758/
Input is a single VC0/DT0x36 row at offset zero, not RPi's combined buffer.
"""

import argparse
import json
from pathlib import Path
from statistics import median


ROWS = 12
COLS = 16
ENTRY_BYTES = 5
HEADER_BYTES = 10
MIN_BYTES = HEADER_BYTES + ROWS * COLS * ENTRY_BYTES


def summarize(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < MIN_BYTES:
        raise ValueError(f"{path}: {len(data)} bytes, need at least {MIN_BYTES}")
    if data[0] != 0 or data[1] >= 0x40:
        raise ValueError(f"{path}: unexpected PDAF header {data[:2].hex()}")
    regions = []
    for index in range(ROWS * COLS):
        start = HEADER_BYTES + index * ENTRY_BYTES
        b0, b1, b2 = data[start:start + 3]
        confidence = (b0 << 3) | (b1 >> 5)
        # Equivalent to the proposed helper's signed high bits and low six bits.
        phase = ((b1 & 0x0f) - (b1 & 0x10)) * 64 + (b2 >> 2)
        if confidence >= 16:
            regions.append((confidence, phase))
    weight = sum(min(confidence, 512) for confidence, _ in regions)
    return {
        "frame": path.name,
        "header": data[:2].hex(),
        "qualified_regions": len(regions),
        "median_confidence": median(confidence for confidence, _ in regions) if regions else None,
        "median_phase": median(phase for _, phase in regions) if regions else None,
        "weighted_mean_phase": round(
            sum(min(confidence, 512) * phase for confidence, phase in regions) / weight, 2
        ) if weight else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    paths = sorted(args.directory.glob("frame-*.bin"))
    if not paths:
        parser.error("No frame-*.bin files found")
    frames = [summarize(path) for path in paths]
    print(json.dumps({
        "source_directory": args.directory.name,
        "layout": {"rows": ROWS, "columns": COLS, "entry_bytes": ENTRY_BYTES},
        "frames": frames,
    }, indent=2))


if __name__ == "__main__":
    main()
