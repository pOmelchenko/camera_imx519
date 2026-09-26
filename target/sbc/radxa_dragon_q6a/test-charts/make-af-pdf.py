"""Place the original indexed PNG on A4 at exactly 300 pixels per inch.

The PNG's compressed scanlines are embedded unchanged. Python's standard
library is sufficient; no image conversion or interpolation is involved.
"""

from pathlib import Path
import struct
import zlib


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "AFTestChart300dpi.png"
OUTPUT = HERE / "AFTestChart300dpi_A4_landscape_100pct.pdf"


def png_parts(data: bytes) -> tuple[int, int, bytes, bytes]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Input is not a PNG")
    position = 8
    palette = b""
    idat = bytearray()
    width = height = None
    while position < len(data):
        length = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        crc = struct.unpack_from(">I", data, position + 8 + length)[0]
        if zlib.crc32(kind + payload) != crc:
            raise ValueError(f"Bad PNG CRC in {kind!r}")
        position += length + 12
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (depth, color, compression, filtering, interlace) != (8, 3, 0, 0, 0):
                raise ValueError("Expected noninterlaced 8-bit indexed PNG")
        elif kind == b"PLTE":
            palette = payload
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"tRNS":
            raise ValueError("Transparent PNG is not supported")
        elif kind == b"IEND":
            break
    if width is None or height is None or not palette or not idat:
        raise ValueError("Incomplete PNG")
    if len(palette) % 3:
        raise ValueError("Invalid RGB palette")
    if len(zlib.decompress(idat)) != (width + 1) * height:
        raise ValueError("Unexpected scanline data size")
    return width, height, palette, bytes(idat)


def pdf_object(number: int, body: bytes) -> bytes:
    return f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"


def make_pdf() -> None:
    width, height, palette, idat = png_parts(SOURCE.read_bytes())
    points_per_mm = 72 / 25.4
    page_width, page_height = 297 * points_per_mm, 210 * points_per_mm
    image_width, image_height = width * 72 / 300, height * 72 / 300
    x, y = (page_width - image_width) / 2, (page_height - image_height) / 2
    if x < 0 or y < 0:
        raise ValueError("Image exceeds A4 landscape")

    content = (f"q\n{image_width:.8f} 0 0 {image_height:.8f} "
               f"{x:.8f} {y:.8f} cm\n/Im0 Do\nQ\n").encode("ascii")
    palette_hex = palette.hex().upper().encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width:.8f} "
         f"{page_height:.8f}] /Resources << /XObject << /Im0 4 0 R >> >> "
         "/Contents 5 0 R >>").encode("ascii"),
        (b"<< /Type /XObject /Subtype /Image "
         + f"/Width {width} /Height {height} ".encode("ascii")
         + b"/ColorSpace [/Indexed /DeviceRGB "
         + str(len(palette) // 3 - 1).encode("ascii") + b" <" + palette_hex + b">] "
         + b"/BitsPerComponent 8 /Filter /FlateDecode "
         + f"/DecodeParms << /Predictor 15 /Colors 1 /BitsPerComponent 8 /Columns {width} >> ".encode("ascii")
         + f"/Length {len(idat)} >>\nstream\n".encode("ascii")
         + idat + b"\nendstream"),
        f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
        + content + b"endstream",
    ]
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(pdf_object(number, body))
    xref = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    result.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    OUTPUT.write_bytes(result)
    print(f"{OUTPUT}: A4 landscape; {width}x{height} pixels at 300 ppi")


if __name__ == "__main__":
    make_pdf()
