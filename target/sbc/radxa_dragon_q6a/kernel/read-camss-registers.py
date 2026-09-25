#!/usr/bin/env python3
"""Read selected SC7280 CAMSS registers while a capture keeps the block powered.

Run as root on Q6A. This tool opens /dev/mem read-only and never writes MMIO.
Configuration offsets come from the pinned camss-csid-gen2.c and
camss-vfe-17x.c sources. Counters and timestamps use the matching CSID 175
register layout in Qualcomm's cam_ife_csid175.h; their interpretation is
provisional until a changing value is observed on this board.
"""

import mmap
import os
import struct
from pathlib import Path


DEVICE_TREE = Path("/sys/bus/platform/devices/acb3000.isp/of_node")
REGISTERS = {
    "csid0": {
        "rx_cfg0": 0x100,
        "rx_cfg1": 0x104,
        "rx_capture_ctrl": 0x108,
        "rx_unmapped_long_header0": 0x120,
        "rx_unmapped_long_header1": 0x124,
        "rx_captured_long_header0": 0x130,
        "rx_captured_long_header1": 0x134,
        "rx_total_packets": 0x160,
        "rx_crc_errors": 0x168,
        "rdi0_cfg0": 0x300,
        "rdi0_ctrl": 0x308,
        "rdi1_cfg0": 0x400,
        "rdi1_ctrl": 0x408,
        "rdi1_status": 0x450,
        "rdi1_format_measure0": 0x478,
        "rdi1_sof_timestamp_low": 0x490,
        "rdi1_eof_timestamp_low": 0x4A0,
        "rdi1_byte_count_ping": 0x4E0,
        "rdi1_byte_count_pong": 0x4E4,
        "rdi2_cfg0": 0x500,
        "rdi2_ctrl": 0x508,
        "rdi2_status": 0x550,
        "rdi2_byte_count_ping": 0x5E0,
        "rdi2_byte_count_pong": 0x5E4,
    },
    "vfe0": {
        "irq_mask0": 0x05C,
        "irq_mask1": 0x060,
        "reg_update_cmd": 0x4AC,
        "bus_irq_mask0": 0x2044,
        "bus_irq_mask1": 0x2048,
        "bus_irq_status0": 0x205C,
        "bus_irq_status1": 0x2060,
        "wm0_status0": 0x2200,
        "wm0_status1": 0x2204,
        "wm0_cfg": 0x2208,
        "wm0_image_addr": 0x2214,
        "wm0_width": 0x221C,
        "wm0_height": 0x2220,
        "wm0_packer": 0x2224,
        "wm0_stride": 0x2228,
        "wm0_frame_inc": 0x2258,
        "wm1_cfg": 0x2308,
        "wm1_frame_inc": 0x2358,
        "wm1_status0": 0x2300,
        "wm2_cfg": 0x2408,
        "wm2_frame_inc": 0x2458,
        "wm2_status0": 0x2400,
    },
}


def resources():
    names = (DEVICE_TREE / "reg-names").read_bytes().rstrip(b"\0").split(b"\0")
    cells = (DEVICE_TREE / "reg").read_bytes()
    if len(cells) != 16 * len(names):
        raise RuntimeError("Unexpected CAMSS device-tree register layout")
    return {
        name.decode(): struct.unpack_from(">QQ", cells, index * 16)
        for index, name in enumerate(names)
    }


def main():
    compatible = (DEVICE_TREE / "compatible").read_bytes()
    if b"qcom,sc7280-camss" not in compatible:
        raise RuntimeError("Unsupported CAMSS compatible")
    regions = resources()
    with open("/dev/mem", "rb", buffering=0) as memory:
        for name, registers in REGISTERS.items():
            base, size = regions[name]
            if base % mmap.PAGESIZE or size < max(registers.values()) + 4:
                raise RuntimeError(f"Unexpected {name} register range")
            print(f"{name} base=0x{base:x} size=0x{size:x}")
            with mmap.mmap(memory.fileno(), size, access=mmap.ACCESS_READ, offset=base) as mmio:
                for label, offset in registers.items():
                    value = struct.unpack_from("<I", mmio, offset)[0]
                    print(f"  {label}=0x{value:08x}")
                    if label in ("rx_unmapped_long_header0", "rx_captured_long_header0") and value:
                        print(f"  {label} VC={value >> 22} DT=0x{(value >> 16) & 0x3f:02x} WC={value & 0xffff}")
                    if label in ("rdi1_cfg0", "rdi2_cfg0"):
                        print(f"  {label[:4]} VC={(value >> 22) & 0x1f} DT=0x{(value >> 16) & 0x3f:02x} enabled={bool(value & (1 << 31))}")


if __name__ == "__main__":
    main()
