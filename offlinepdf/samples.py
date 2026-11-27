"""Generate realistic-looking sample documents (for the self-test and screenshots)."""

from __future__ import annotations

import io
import random
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PALETTE = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#a855f7"]


def _photo(width: int, height: int, seed: int) -> Image.Image:
    rng = random.Random(seed)
    top = tuple(rng.randrange(60, 200) for _ in range(3))
    bottom = tuple(rng.randrange(20, 120) for _ in range(3))
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        f = y / height
        draw.line([(0, y), (width, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * f) for i in range(3)))
    for _ in range(14):
        r = rng.randrange(width // 14, width // 5)
        x, y = rng.randrange(width), rng.randrange(height)
        color = tuple(rng.randrange(120, 255) for _ in range(3))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
    # a horizon
    draw.polygon([(0, height), (0, int(height * 0.7)), (width * 0.4, int(height * 0.55)), (width, int(height * 0.75)), (width, height)], fill=(30, 60, 50))
    return image


def _text_lines(pdf: canvas.Canvas, x: float, y: float, width: float, lines: int, rng: random.Random) -> float:
    pdf.setFillColor(HexColor("#c9cdd8"))
    for _ in range(lines):
        pdf.roundRect(x, y, width * rng.uniform(0.55, 1.0), 6, 3, stroke=0, fill=1)
        y -= 14
    return y


def report(path: Path, pages: int = 8, title: str = "Annual Report 2026", seed: int = 7) -> Path:
    rng = random.Random(seed)
    w, h = A4
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle(title)
    pdf.setAuthor("OfflinePDF sample")
    for number in range(1, pages + 1):
        color = HexColor(PALETTE[(number - 1) % len(PALETTE)])
        if number == 1:
            pdf.setFillColor(color)
            pdf.rect(0, 0, w, h, stroke=0, fill=1)
            pdf.setFillColor(HexColor("#ffffff"))
            pdf.setFont("Helvetica-Bold", 40)
            pdf.drawString(56, h - 260, title)
            pdf.setFont("Helvetica", 16)
            pdf.drawString(58, h - 296, "Prepared with OfflinePDF sample generator")
            pdf.setFillAlpha(0.18)
            pdf.circle(w - 80, 120, 180, stroke=0, fill=1)
            pdf.setFillAlpha(1)
        else:
            pdf.setFillColor(color)
            pdf.rect(0, h - 64, w, 64, stroke=0, fill=1)
            pdf.setFillColor(HexColor("#ffffff"))
            pdf.setFont("Helvetica-Bold", 18)
            pdf.drawString(40, h - 42, f"{number - 1}. Section {number - 1}")
            y = _text_lines(pdf, 40, h - 110, w - 80, 8, rng)
            if number % 2 == 0:
                # bar chart
                base = y - 190
                for i in range(7):
                    bar_h = rng.uniform(40, 170)
                    pdf.setFillColor(HexColor(PALETTE[i % len(PALETTE)]))
                    pdf.roundRect(60 + i * 68, base, 44, bar_h, 4, stroke=0, fill=1)
                y = base - 30
            else:
                buffer = io.BytesIO()
                _photo(900, 560, seed + number).save(buffer, "JPEG", quality=85)
                buffer.seek(0)
                pdf.drawImage(ImageReader(buffer), 40, y - 300, width=w - 80, height=(w - 80) * 560 / 900)
                y -= 330
            _text_lines(pdf, 40, y, w - 80, 10, rng)
            pdf.setFillColor(HexColor("#8a90a0"))
            pdf.setFont("Helvetica", 9)
            pdf.drawCentredString(w / 2, 28, f"{title}  ·  {number}")
        pdf.showPage()
    pdf.save()
    return path


def invoice(path: Path, number: int = 1043) -> Path:
    rng = random.Random(number)
    w, h = A4
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle(f"Invoice {number}")
    pdf.setFillColor(HexColor("#0f172a"))
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(48, h - 80, "INVOICE")
    pdf.setFont("Helvetica", 11)
    pdf.drawRightString(w - 48, h - 72, f"No. {number}")
    pdf.setFillColor(HexColor("#10b981"))
    pdf.rect(48, h - 100, 120, 5, stroke=0, fill=1)
    y = h - 170
    for i in range(9):
        pdf.setFillColor(HexColor("#f1f5f9") if i % 2 else HexColor("#ffffff"))
        pdf.rect(48, y - 6, w - 96, 26, stroke=0, fill=1)
        pdf.setFillColor(HexColor("#334155"))
        pdf.drawString(58, y + 2, f"Item {i + 1}")
        pdf.drawRightString(w - 58, y + 2, f"{rng.randrange(20, 900)}.00")
        y -= 26
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawRightString(w - 58, y - 30, "Total  4,280.00")
    pdf.showPage()
    pdf.save()
    return path


def brochure(path: Path, pages: int = 3) -> Path:
    w, h = landscape(A4)
    pdf = canvas.Canvas(str(path), pagesize=(w, h))
    pdf.setTitle("Product Brochure")
    for number in range(pages):
        buffer = io.BytesIO()
        _photo(1200, 800, 40 + number).save(buffer, "JPEG", quality=85)
        buffer.seek(0)
        pdf.drawImage(ImageReader(buffer), 0, 0, width=w, height=h)
        pdf.setFillColor(HexColor("#ffffff"))
        pdf.setFont("Helvetica-Bold", 34)
        pdf.drawString(50, 60, ["Discover", "Create", "Share"][number % 3])
        pdf.showPage()
    pdf.save()
    return path


def photo_files(folder: Path, count: int = 4) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(count):
        path = folder / f"photo_{i + 1:02d}.jpg"
        _photo(1600, 1067 if i % 2 == 0 else 2000, 90 + i).save(path, "JPEG", quality=88)
        paths.append(path)
    return paths


def make_all(folder: Path) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    return {
        "report": report(folder / "Annual Report 2026.pdf"),
        "invoice": invoice(folder / "Invoice 1043.pdf"),
        "brochure": brochure(folder / "Product Brochure.pdf"),
    }
