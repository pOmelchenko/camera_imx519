#!/usr/bin/env python3
"""Capture one packed Bayer RAW10 frame from the IMX519 on the selected Q6A connector."""
import argparse
from contextlib import contextmanager
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from tempfile import mkdtemp
from typing import NamedTuple

from ports import PORTS

MODES = ("1920x1080", "4656x3496", "3840x2160", "2328x1748", "1280x720")
FOURCC = {"RGGB": "pRAA", "GRBG": "pgAA", "GBRG": "pGAA", "BGGR": "pBAA"}


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def find_camera(port, phy):
    # Match this physical receiver even when another IMX519 uses the same I2C address.
    detected = []
    for media in sorted(Path("/dev").glob("media[0-9]*")):
        graph = subprocess.check_output(["media-ctl", "-d", media, "-p"], text=True)
        for entity in graph.split("- entity ")[1:]:
            sensor = re.match(r"\d+: (imx519 \d+-001a) \(", entity)
            if sensor:
                if re.search(rf'-> "{phy}":0 \[ENABLED\b', entity):
                    return media, sensor[1]
                detected.append(f"{media}: {entity.splitlines()[0]}")
    if detected:
        raise ValueError(f"Для {port.upper()} нет связи IMX519 → {phy}. Обнаруженные сенсоры:\n"
                         + "\n".join(detected)
                         + "\nПри 0 link посмотрите, какой сенсор ожидает qcom-camss в текущей загрузке:\n"
                           "sudo cat /sys/kernel/debug/v4l2-async/pending_async_subdevices")
    raise ValueError(f"В media graph нет связи imx519 → {phy}. Проверьте probe и порт {port.upper()}.")


def format_value(description, field, pattern):
    match = re.search(rf"^\s*{field}\s*:\s*({pattern})", description, re.MULTILINE)
    if not match:
        raise ValueError(f"Не удалось прочитать {field} из v4l2-ctl.")
    return match[1]


class Link(NamedTuple):
    source: str
    pad: int
    sink: str
    sink_pad: int
    enabled: bool

    def setting(self, enable):
        return f'"{self.source}":{self.pad} -> "{self.sink}":{self.sink_pad} [{int(enable)}]'


def select_route(graph, sensor, phy):
    links = []
    for section in graph.split("- entity ")[1:]:
        name = section.split(": ", 1)[1].split(" (", 1)[0]
        pad = None
        for line in section.splitlines()[1:]:
            m = re.match(r"\s*pad(\d+):", line)
            if m:
                pad = int(m[1])
            m = re.match(r'\s*-> "([^"]+)":(\d+) \[([^\]]*)\]', line)
            if m and pad is not None:
                flags = {flag.strip() for flag in m[3].split(",")}
                links.append(Link(name, pad, m[1], int(m[2]), "ENABLED" in flags))
    if Link(sensor, 0, phy, 0, True) not in links:
        raise ValueError(f"Связь {sensor} → {phy} изменилась перед захватом.")
    active = [link for link in links if link.enabled]
    # On Q6A use VC0, RDI0 and the matching CSID/VFE pair. Keep foreign links intact.
    candidates = []
    for first in links:
        csid = re.fullmatch(r"msm_csid(\d+)", first.sink)
        if first.source != phy or first.pad != 1 or first.sink_pad != 0 or not csid:
            continue
        rdi = f"msm_vfe{csid[1]}_rdi0"
        for second in links:
            if (second.source, second.pad, second.sink, second.sink_pad) != (first.sink, 1, rdi, 0):
                continue
            related = [l for l in active if l.source in (phy, first.sink) or l.sink == first.sink
                       or (l.source.startswith("msm_csid") and l.sink.startswith(f"msm_vfe{csid[1]}_"))]
            if any(l not in (first, second) for l in related) or (second.enabled and not first.enabled):
                continue
            video = next((l.sink for l in active if l.source == rdi and l.pad == 1
                          and re.fullmatch(r"msm_vfe\d+_video\d+", l.sink)), None)
            if video:
                candidates.append((not first.enabled, int(csid[1]), first, second, video))
    if not candidates:
        raise ValueError("Нет свободного маршрута CSID/VFE RDI0. Активные связи камер сохранены.")
    _, _, first, second, video = min(candidates)
    return first, second, video


@contextmanager
def lens_position(ctl, sensor, focus):
    if focus is None:
        yield
        return
    # The VCM is on the same CCI bus as this sensor. The driver parks the
    # lens on runtime suspend, so keep one handle open throughout streaming.
    bus = sensor.split()[1].split("-")[0]
    path = subprocess.check_output([*ctl, "-e", f"ak7375 {bus}-000c"], text=True).strip()
    with open(path, "rb", buffering=0):
        run("v4l2-ctl", "-d", path, f"--set-ctrl=focus_absolute={focus}")
        yield


def capture(port, mode=MODES[0], focus=None):
    import fcntl
    os.environ["LC_ALL"] = "C"
    phy = f"msm_csiphy{PORTS[port][1]}"
    media, sensor = find_camera(port, phy)
    ctl = ["media-ctl", "-d", media]
    with media.open("rb", buffering=0) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        graph = subprocess.check_output([*ctl, "-p"], text=True)
        first, second, video = select_route(graph, sensor, phy)
        print(f"{media}: {sensor} → {phy} → {first.sink} → {second.sink}", flush=True)
        created = []
        try:
            for link in (first, second):
                if not link.enabled:
                    run(*ctl, "-l", link.setting(True))
                    created.append(link)
            with lens_position(ctl, sensor, focus):
                capture_frame(ctl, sensor, phy, first.sink, second.sink, video, mode, focus)
        finally:
            for link in reversed(created):
                result = subprocess.run([*ctl, "-l", link.setting(False)], check=False)
                if result.returncode:
                    print(f"Не удалось освободить связь {link.source} → {link.sink}.", file=sys.stderr)


def capture_frame(ctl, sensor, phy, csid, rdi, video_entity, mode, focus):
    width, height = map(int, mode.split("x"))
    source = f'"{sensor}":0'
    run(*ctl, "-V", f"{source} [fmt:SRGGB10_1X10/{mode} field:none]")
    active = subprocess.check_output([*ctl, "--get-v4l2", source], text=True)
    # IMX519 derives the actual Bayer order from the current HFLIP/VFLIP.
    match = re.search(r"fmt:S(RGGB|GRBG|GBRG|BGGR)10_1X10/(\d+x\d+)\b", active)
    if not match or match[2] != mode:
        raise ValueError(f"IMX519 не согласовал RAW10 {mode}: {active.strip()}")
    order = match[1]
    for entity, pad in [(phy, 0), (csid, 0), (csid, 1), (rdi, 0)]:
        run(*ctl, "-V", f'"{entity}":{pad} [fmt:S{order}10_1X10/{mode} field:none]')

    video = subprocess.check_output([*ctl, "-e", video_entity], text=True).strip()
    v4l2 = ["v4l2-ctl", "-d", video]
    fourcc = FOURCC[order]
    run(*v4l2, f"--set-fmt-video=width={width},height={height},pixelformat={fourcc}")
    fmt = subprocess.check_output([*v4l2, "--get-fmt-video"], text=True)
    print(video, fmt, sep="\n", flush=True)
    if (format_value(fmt, "Pixel Format", r"'[^']+'") != f"'{fourcc}'" or
            format_value(fmt, "Width/Height", r"\d+/\d+") != f"{width}/{height}"):
        raise ValueError("CAMSS согласовал другой формат или размер кадра.")
    stride = int(format_value(fmt, "Bytes per Line", r"\d+"))
    size = int(format_value(fmt, "Size Image", r"\d+"))
    row_bytes = width * 5 // 4
    if stride < row_bytes or size < stride * height:
        raise ValueError(f"Некорректные параметры буфера: stride={stride}, sizeimage={size}.")

    output = Path(mkdtemp(prefix="imx519-", dir="."))
    raw = output / "frame.raw"
    print(f"Захват в {output.resolve()}", flush=True)
    run(*v4l2, "--stream-mmap=4", "--stream-count=1", f"--stream-to={raw}", timeout=15)
    frame = raw.read_bytes()
    if len(frame) != size:
        raise ValueError(f"Получено {len(frame)} байт, ожидалось {size}.")

    with (output / "preview.ppm").open("wb") as preview:
        write_preview(preview, frame, width, height, stride, order)
    metadata = {"sensor": sensor, "csiphy": phy, "width": width, "height": height,
                "fourcc": fourcc, "stride": stride, "sizeimage": size, "requested_focus": focus}
    (output / "frame.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"RAW10 и 8-битное превью сохранены в {output.resolve()}")


def write_preview(preview, frame, width, height, stride, order):
    """One RGB pixel per 2x2 Bayer block, using the high eight bits of packed RAW10."""
    preview.write(f"P6\n{width // 2} {height // 2}\n255\n".encode("ascii"))
    row_bytes = width * 5 // 4
    for y in range(0, height, 2):
        top = bytearray(frame[y * stride:y * stride + row_bytes])
        bottom = bytearray(frame[(y + 1) * stride:(y + 1) * stride + row_bytes])
        del top[4::5]
        del bottom[4::5]
        rgb = bytearray(width // 2 * 3)
        planes = (top[::2], top[1::2], bottom[::2], bottom[1::2])
        rgb[0::3] = planes[order.index("R")]
        green = (planes[order.index("G")], planes[order.rindex("G")])
        rgb[1::3] = bytes((a + b) // 2 for a, b in zip(*green))
        rgb[2::3] = planes[order.index("B")]
        preview.write(rgb)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=str.lower, choices=PORTS, default="cam3",
                        help="разъём Q6A (по умолчанию cam3/J7)")
    parser.add_argument("--size", choices=MODES, default=MODES[0], help="режим IMX519")
    parser.add_argument("--focus", type=int, help="ручной focus_absolute для AK7375 (0…4095)")
    args = parser.parse_args()
    if args.focus is not None and not 0 <= args.focus <= 4095:
        parser.error("--focus должен быть от 0 до 4095")
    try:
        capture(args.port, args.size, args.focus)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
