#!/usr/bin/env python3
"""Summarize a cam autofocus capture log and detect sequence gaps."""

import argparse
import json
import re
from pathlib import Path

FRAME = re.compile(r"^(\d+\.\d+) \([^)]*\) cam0-stream0 seq: (\d+)")
POSITION = re.compile(r"Contrast AF position (\d+) score ([\d.]+) state (\d+)")
STATE = re.compile(r"\tAfState = (\d+)")
PAUSE = re.compile(r"\tAfPauseState = (\d+)")


def summarize(path):
    frames = []
    focus = []
    states = {}
    pauses = {}
    errors = []
    for line in path.read_text(errors="replace").splitlines():
        if match := FRAME.search(line):
            frames.append((float(match[1]), int(match[2])))
        if match := POSITION.search(line):
            focus.append(dict(raw=int(match[1]), score=float(match[2]), state=int(match[3])))
        if match := STATE.search(line):
            states[match[1]] = states.get(match[1], 0) + 1
        if match := PAUSE.search(line):
            pauses[match[1]] = pauses.get(match[1], 0) + 1
        if " ERROR " in line or " FATAL " in line:
            errors.append(line)
    gaps = [[a[1], b[1]] for a, b in zip(frames, frames[1:]) if b[1] != a[1] + 1]
    duration = frames[-1][0] - frames[0][0] if len(frames) > 1 else None
    return dict(file=str(path), frames=len(frames),
                first_sequence=frames[0][1] if frames else None,
                last_sequence=frames[-1][1] if frames else None,
                sequence_gaps=gaps, duration_seconds=duration,
                average_fps=(len(frames) - 1) / duration if duration else None,
                autofocus_results=focus, af_states=states, af_pause_states=pauses,
                errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([summarize(path) for path in args.logs], indent=2))


if __name__ == "__main__":
    main()
