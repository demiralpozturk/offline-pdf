from __future__ import annotations

import io
import random
from pathlib import Path

import pikepdf
import pytest
from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def make_pdf(path: Path, pages: int = 5, *, label: str = "Page", size=A4, title: str = "") -> Path:
    pdf = canvas.Canvas(str(path), pagesize=size)
    if title:
        pdf.setTitle(title)
        pdf.setAuthor("Test Author")
    for number in range(1, pages + 1):
        pdf.setFont("Helvetica", 28)
        pdf.drawString(72, size[1] - 120, f"{label} {number}")
        pdf.bookmarkPage(f"p{number}")
        pdf.addOutlineEntry(f"{label} {number}", f"p{number}", level=0)
        pdf.showPage()
    pdf.save()
    return path


def noisy_photo(width: int = 2400, height: int = 1800, seed: int = 1) -> Image.Image:
    rng = random.Random(seed)
    image = Image.new("RGB", (width // 8, height // 8))
    image.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(image.width * image.height)])
    return image.resize((width, height), Image.BICUBIC)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return make_pdf(tmp_path / "sample.pdf", 5, title="Sample Title")


@pytest.fixture
def second_pdf(tmp_path: Path) -> Path:
    return make_pdf(tmp_path / "second.pdf", 3, label="Second", size=landscape(A4))


@pytest.fixture
def rotated_pdf(tmp_path: Path) -> Path:
    path = make_pdf(tmp_path / "rotated_src.pdf", 2)
    out = tmp_path / "rotated.pdf"
    with pikepdf.open(path) as pdf:
        pdf.pages[1].rotate(90, relative=True)
        pdf.save(out)
    return out


@pytest.fixture
def photo_pdf(tmp_path: Path) -> Path:
    """A PDF with a large, losslessly stored photo: lots of room to compress."""
    path = tmp_path / "photo.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4)
    buffer = io.BytesIO()
    noisy_photo().save(buffer, "PNG")
    buffer.seek(0)
    pdf.drawImage(ImageReader(buffer), 36, 200, width=520, height=390)
    pdf.drawString(72, 100, "Photo page")
    pdf.showPage()
    pdf.save()
    return path


@pytest.fixture
def jpeg_file(tmp_path: Path) -> Path:
    path = tmp_path / "photo.jpg"
    noisy_photo(1200, 900, seed=2).save(path, "JPEG", quality=85)
    return path


@pytest.fixture
def png_file(tmp_path: Path) -> Path:
    path = tmp_path / "logo.png"
    image = Image.new("RGBA", (300, 500), (0, 0, 0, 0))
    for x in range(100, 200):
        for y in range(100, 400):
            image.putpixel((x, y), (40, 90, 200, 255))
    image.save(path)
    return path


@pytest.fixture
def encrypted_pdf(tmp_path: Path, sample_pdf: Path) -> Path:
    out = tmp_path / "locked.pdf"
    with pikepdf.open(sample_pdf) as pdf:
        pdf.save(out, encryption=pikepdf.Encryption(owner="owner-pw", user="secret", R=6))
    return out
