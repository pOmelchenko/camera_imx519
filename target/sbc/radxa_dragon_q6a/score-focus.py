#!/usr/bin/env python3
"""Compare green-channel gradient energy in cam P6 images of a static scene.

This is a sharpness heuristic, not an optical calibration or a continuous AF.
Use the same ROI, lighting, exposure and scene in all compared frames.
"""
import argparse
import json
from pathlib import Path


def score(path, roi):
    with path.open("rb") as stream:
        if stream.readline().strip() != b"P6":
            raise ValueError(f"{path}: expected a P6 image written by cam")
        width, height = map(int, stream.readline().split())
        if stream.readline().strip() != b"255":
            raise ValueError("Only 8-bit P6 images are supported")
        pixels = stream.read()
    if len(pixels) != width * height * 3:
        raise ValueError(f"{path}: incomplete frame")
    x, y, w, h = roi
    left, top = int(x * width), int(y * height)
    right, bottom = min(int((x+w)*width), width-1), min(int((y+h)*height), height-1)
    total = energy = count = 0
    for row in range(top, bottom):
        for col in range(left, right):
            offset = (row * width + col) * 3 + 1
            green = pixels[offset]
            total += green
            energy += (green-pixels[offset+3])**2 + (green-pixels[offset+width*3])**2
            count += 1
    if not count:
        raise ValueError("ROI is empty")
    mean = total / count
    return dict(file=str(path), mean_green=mean, gradient_energy=energy/count,
                normalized_energy=energy/count/max(mean**2, 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roi", nargs=4, type=float, default=[0.02, 0.1, 0.46, 0.8],
                        metavar=("X", "Y", "WIDTH", "HEIGHT"))
    parser.add_argument("images", nargs="+", type=Path)
    args = parser.parse_args()
    x, y, w, h = args.roi
    if not (0 <= x < 1 and 0 <= y < 1 and w > 0 and h > 0 and x+w <= 1 and y+h <= 1):
        parser.error("ROI must lie within the image, in normalized coordinates")
    results = [score(path, args.roi) for path in args.images]
    print(json.dumps(dict(roi=args.roi, results=results,
                         best=max(results, key=lambda row: row['normalized_energy'])['file']), indent=2))


if __name__ == "__main__":
    main()
