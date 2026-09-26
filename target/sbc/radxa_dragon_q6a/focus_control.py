#!/usr/bin/env python3
"""Write a libcamera cam script for a manual AK7375 focus code.

The raw-code-to-dioptre mapping is provisional for this IMX519 runtime; it
is a control mapping, not a calibrated subject distance.
"""

import argparse
from pathlib import Path


MAX_RAW_CODE = 4095
MAX_DIOPTERS = 15.0


def script_for(code):
    if isinstance(code, bool) or not isinstance(code, int) or not 0 <= code <= MAX_RAW_CODE:
        raise ValueError("focus code must be an integer from 0 to 4095")
    diopters = code * MAX_DIOPTERS / MAX_RAW_CODE
    return f"frames:\n  - 0:\n      AfMode: 0\n      LensPosition: {diopters:.6f}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("code", type=int, help="AK7375 raw focus code, 0..4095")
    parser.add_argument("output", type=Path, help="output YAML for cam --script")
    args = parser.parse_args()
    try:
        content = script_for(args.code)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_text(content)


if __name__ == "__main__":
    main()
