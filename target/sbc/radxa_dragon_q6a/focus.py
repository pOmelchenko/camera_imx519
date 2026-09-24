#!/usr/bin/env python3
"""Hold AK7375 at a manual position while a command runs; restore on exit.

Example: python3 focus.py 1024 -- bash capture.sh rgb 30
The lens subdevice must remain open: closing it parks the lens via runtime PM.
Position is a raw driver code (0..4095), not distance or dioptres. No continuous AF.
"""
import argparse
import fcntl
import os
from pathlib import Path
import struct
import subprocess
import time

# Linux arm64 V4L2 ABI, verified against the target's installed Linux headers.
VIDIOC_G_CTRL = 0xC008561B
VIDIOC_S_CTRL = 0xC008561C
V4L2_CID_FOCUS_ABSOLUTE = 0x009A090A


def control(fd, request, value=0):
    data = bytearray(struct.pack("=Ii", V4L2_CID_FOCUS_ABSOLUTE, value))
    fcntl.ioctl(fd, request, data, True)
    return struct.unpack("=Ii", data)[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("position", type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not 0 <= args.position <= 4095:
        parser.error("position must be a driver code in 0..4095")
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command to run while holding focus is required")
    lenses = [p for p in Path("/sys/class/video4linux").glob("v4l-subdev*")
              if (p / "name").read_text().split()[0] == "ak7375"]
    if len(lenses) != 1:
        parser.error(f"expected one AK7375 lens, found {len(lenses)}")
    node = Path("/dev") / lenses[0].name
    fd = os.open(node, os.O_RDWR | os.O_CLOEXEC)
    try:
        original = control(fd, VIDIOC_G_CTRL)
        try:
            control(fd, VIDIOC_S_CTRL, args.position)
            readback = control(fd, VIDIOC_G_CTRL)
            if readback != args.position:
                raise RuntimeError(f"focus readback {readback} != {args.position}")
            print(f"Lens {node}: focus {original} -> {readback}; FD held open", flush=True)
            time.sleep(0.2)
            return subprocess.call(command)
        finally:
            control(fd, VIDIOC_S_CTRL, original)
            print(f"Lens control restored to {original}; closing FD", flush=True)
    finally:
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
