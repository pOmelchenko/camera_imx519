"""Make a Fotosav-style A4 chart with exact 1 mm axial-depth divisions.

The retained PNG supplies the layout. The scale, contrast strips, central
target and support-flap boundary are rebuilt as PDF vectors. The scale assumes
a 45 degree angle between the target plane and the ruler plane.
"""

import math
from pathlib import Path
import runpy


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "AFTestChart300dpi.png"
OUTPUT = HERE / "AFTestChart_1mm_depth_45deg_A4_100pct.pdf"
common = runpy.run_path(str(HERE / "make-af-pdf.py"), run_name="af_pdf_common")
png_parts = common["png_parts"]
pdf_object = common["pdf_object"]


def make_pdf() -> None:
    width, height, palette, idat = png_parts(SOURCE.read_bytes())
    if (width, height) != (2884, 1781):
        raise ValueError("Scale overlay expects the retained Fotosav 2884x1781 PNG")

    pt_per_mm = 72 / 25.4
    pt_per_pixel = 72 / 300
    page_width, page_height = 297 * pt_per_mm, 210 * pt_per_mm
    image_width, image_height = width * pt_per_pixel, height * pt_per_pixel
    image_left = (page_width - image_width) / 2
    image_bottom = (page_height - image_height) / 2
    center_x = image_left + 1543 * pt_per_pixel
    one_mm_depth_on_paper = math.sqrt(2) * pt_per_mm

    def sx(pixel: float) -> float:
        return image_left + pixel * pt_per_pixel

    def sy(pixel: float) -> float:
        return image_bottom + (height - pixel) * pt_per_pixel

    def source_rect(left: float, top: float, right: float, bottom: float) -> str:
        return (f"{sx(left):.8f} {sy(bottom):.8f} "
                f"{(right - left) * pt_per_pixel:.8f} "
                f"{(bottom - top) * pt_per_pixel:.8f} re f")

    def source_line(x1: float, y1: float, x2: float, y2: float,
                    width_pixels: float) -> str:
        return (f"{width_pixels * pt_per_pixel:.8f} w "
                f"{sx(x1):.8f} {sy(y1):.8f} m "
                f"{sx(x2):.8f} {sy(y2):.8f} l S")

    content = [
        "1 g",
        f"0 0 {page_width:.8f} {page_height:.8f} re f",
        "q",
        f"{image_width:.8f} 0 0 {image_height:.8f} {image_left:.8f} {image_bottom:.8f} cm",
        "/Im0 Do",
        "Q",
        # Remove the old approximate scale and its unrelated stripe pitch.
        "1 g",
        f"{sx(0):.8f} {sy(874):.8f} {image_width:.8f} {sy(545) - sy(874):.8f} re f",
        # The original title/credit is documented alongside the source PNG.
        source_rect(25, 20, 1050, 190),
        # Align the target and the support flap on one continuous outline.
        source_rect(1537, 885, 2315, 1781),
        "0 g 0 G",
    ]

    # The source outer cut line and the second, empty support flap are raster.
    # Clear them so all four sides and both flap joins share vector endpoints.
    content.extend([
        "1 g",
        source_rect(0, 0, 8, 1781),
        source_rect(2876, 0, 2884, 1781),
        source_rect(0, 0, 2884, 8),
        source_rect(0, 1772, 2884, 1781),
        source_rect(1529, 0, 1559, 540),
        source_rect(276, 1480, 725, 1781),
        "0 g 0 G",
    ])

    # Central target and flap. The original thin and thick guide lines had
    # slightly different endpoints; the vector lines share exact coordinates.
    left, right = 1544.0, 2310.0
    top, flap_top, bottom = 890.0, 1475.0, 1780.0
    content.extend([
        source_line(left, top, right, top, 2),
        source_line(right, top, right, bottom, 2),
        source_line(left, top, left, 1118, 7),
        source_line(left, 1118, left, bottom, 2),
    ])
    for x, stroke_pixels in ((1865, 9), (1929, 3), (1991, 9)):
        content.append(source_line(x, top, x, flap_top, stroke_pixels))
    for y, stroke_pixels in ((1118, 9), (1185, 3), (1245, 9)):
        content.append(source_line(left, y, right, y, stroke_pixels))
    content.extend([
        source_rect(1906, 982, 1951, 1381),
        source_rect(1726, 1160, 2131, 1205),
        source_line(left, flap_top, right, flap_top, 2),
    ])

    # Every long bar corresponds to 1 mm of axial depth at exactly 45 degrees.
    min_step = math.ceil((image_left - center_x) / one_mm_depth_on_paper)
    max_step = math.floor((image_left + image_width - center_x) / one_mm_depth_on_paper)
    content.append(f"{0.25 * pt_per_mm:.8f} w")
    for step in range(min_step, max_step + 1):
        x = center_x + step * one_mm_depth_on_paper
        content.append(f"{x:.8f} {sy(630):.8f} m {x:.8f} {sy(866):.8f} l S")

    # Short ticks above the bars: minor 1 mm, medium 5 mm, major 10 mm.
    for depth_mm in range(-50, 51):
        x = center_x + depth_mm * one_mm_depth_on_paper
        if depth_mm % 10 == 0:
            top_pixel, stroke_mm = 590, 0.22
        elif depth_mm % 5 == 0:
            top_pixel, stroke_mm = 598, 0.18
        else:
            top_pixel, stroke_mm = 606, 0.13
        content.append(
            f"{stroke_mm * pt_per_mm:.8f} w {x:.8f} {sy(620):.8f} m "
            f"{x:.8f} {sy(top_pixel):.8f} l S"
        )
        if depth_mm % 5 == 0:
            value = abs(depth_mm) / 10
            label = str(int(value)) if depth_mm % 10 == 0 else f"{value:.1f}"
            label_width = 3.89 if len(label) == 1 else 9.73
            content.extend([
                "BT /F2 7 Tf",
                f"1 0 0 1 {x - label_width / 2:.8f} {sy(568):.8f} Tm",
                f"({label}) Tj ET",
            ])
    content.extend([
        "BT /F1 7 Tf",
        f"1 0 0 1 {center_x + 50 * one_mm_depth_on_paper + 13:.8f} "
        f"{sy(568):.8f} Tm",
        "(cm) Tj ET",
        # A separate vector rule for checking that the printer used 100% scale.
        f"{0.22 * pt_per_mm:.8f} w",
        f"{10 * pt_per_mm:.8f} {9 * pt_per_mm:.8f} m "
        f"{110 * pt_per_mm:.8f} {9 * pt_per_mm:.8f} l S",
    ])
    for mark_mm in (10, 110):
        content.append(
            f"{mark_mm * pt_per_mm:.8f} {7.5 * pt_per_mm:.8f} m "
            f"{mark_mm * pt_per_mm:.8f} {10.5 * pt_per_mm:.8f} l S"
        )
    content.extend([
        "BT /F1 7 Tf",
        f"1 0 0 1 {10 * pt_per_mm:.8f} {13 * pt_per_mm:.8f} Tm",
        "(100 mm print check / Actual Size) Tj ET",
    ])

    # Draw the common cut perimeter last so that no raster seams remain at
    # the scale band or where the two lower support flaps meet the bottom.
    content.extend([
        source_line(282, 1487, 719, 1487, 3),
        source_line(282, 1487, 282, bottom, 3),
        source_line(719, 1487, 719, bottom, 3),
        source_line(1, 1, 1, bottom, 2),
        source_line(2882, 1, 2882, bottom, 2),
        source_line(1, bottom, 2882, bottom, 2),
        source_line(1, 1, 1519, 1, 2),
        source_line(1567, 1, 2882, 1, 2),
        source_line(1543, 1, 1543, 532, 5),
        source_line(1543, 84, 1543, 438, 16),
    ])
    drawing = ("\n".join(content) + "\n").encode("ascii")

    palette_hex = palette.hex().upper().encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width:.8f} "
         f"{page_height:.8f}] /Resources << /XObject << /Im0 4 0 R >> "
         "/Font << /F1 6 0 R /F2 7 0 R >> >> /Contents 5 0 R >>").encode("ascii"),
        (b"<< /Type /XObject /Subtype /Image "
         + f"/Width {width} /Height {height} ".encode("ascii")
         + b"/ColorSpace [/Indexed /DeviceRGB "
         + str(len(palette) // 3 - 1).encode("ascii") + b" <" + palette_hex + b">] "
         + b"/BitsPerComponent 8 /Filter /FlateDecode "
         + f"/DecodeParms << /Predictor 15 /Colors 1 /BitsPerComponent 8 /Columns {width} >> ".encode("ascii")
         + f"/Length {len(idat)} >>\nstream\n".encode("ascii")
         + idat + b"\nendstream"),
        f"<< /Length {len(drawing)} >>\nstream\n".encode("ascii")
        + drawing + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(pdf_object(number, body))
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    OUTPUT.write_bytes(pdf)
    print(f"{OUTPUT}: A4 landscape; 1 mm depth = {math.sqrt(2):.9f} mm on paper")


if __name__ == "__main__":
    make_pdf()
