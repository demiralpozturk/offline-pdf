from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from offlinepdf.core import (
    PasswordRequiredError,
    WrongPasswordError,
    compress,
    get_info,
    images_to_pdf,
    is_encrypted,
    page_numbers,
    pdf_to_images,
    protect,
    read_metadata,
    set_metadata,
    strip_metadata,
    unlock,
    watermark,
)
from offlinepdf.core.render import page_text


def test_compress_photo_pdf_is_smaller_and_valid(tmp_path, photo_pdf):
    result = compress(photo_pdf, tmp_path / "small.pdf", level="medium")
    assert result.new_size < result.original_size * 0.6
    assert result.saved_percent > 40
    assert "Photo page" in page_text(result.path, 0)


def test_compress_never_grows(tmp_path, sample_pdf):
    result = compress(sample_pdf, tmp_path / "c.pdf", level="high")
    assert result.new_size <= result.original_size
    with pikepdf.open(result.path) as pdf:
        assert len(pdf.pages) == 5


def test_compress_lossless_level(tmp_path, photo_pdf):
    result = compress(photo_pdf, tmp_path / "l.pdf", level="low")
    assert result.new_size <= result.original_size


def test_images_to_pdf_fit_and_a4(tmp_path, jpeg_file, png_file):
    fit = images_to_pdf([jpeg_file, png_file], tmp_path / "fit.pdf")
    with pikepdf.open(fit) as pdf:
        assert len(pdf.pages) == 2
        w, h = (float(v) for v in pdf.pages[0].mediabox[2:])
        assert w > h  # landscape photo -> landscape page
    # The JPEG is embedded as-is, so the PDF stays close to the JPEG size.
    assert fit.stat().st_size < jpeg_file.stat().st_size + png_file.stat().st_size + 60_000

    a4 = images_to_pdf([png_file], tmp_path / "a4.pdf", page_size="a4", margin_mm=10)
    with pikepdf.open(a4) as pdf:
        w, h = (round(float(v)) for v in pdf.pages[0].mediabox[2:])
        assert (w, h) == (595, 842)


def test_pdf_to_images_png_and_jpg(tmp_path, sample_pdf):
    pngs = pdf_to_images(sample_pdf, tmp_path / "png", dpi=72)
    assert len(pngs) == 5 and pngs[0].name == "sample_page001.png"
    with Image.open(pngs[0]) as image:
        assert abs(image.width - 595) <= 2
    jpgs = pdf_to_images(sample_pdf, tmp_path / "jpg", fmt="jpg", dpi=144, pages="2-3")
    assert [p.name for p in jpgs] == ["sample_page002.jpg", "sample_page003.jpg"]
    with Image.open(jpgs[0]) as image:
        assert abs(image.width - 1190) <= 3


def test_watermark_turkish_text_is_searchable(tmp_path, sample_pdf):
    out = watermark(sample_pdf, tmp_path / "w.pdf", "GİZLİDİR şğü", opacity=0.3)
    text = page_text(out, 0)
    assert "Page 1" in text
    assert "GİZLİDİR" in text and "şğü" in text


def test_watermark_tiled_on_rotated_page(tmp_path, rotated_pdf):
    out = watermark(rotated_pdf, tmp_path / "w.pdf", "DRAFT", tiled=True, angle=30, under=True)
    assert "DRAFT" in page_text(out, 1)


def test_page_numbers(tmp_path, sample_pdf):
    out = page_numbers(sample_pdf, tmp_path / "n.pdf", template="{n} / {total}")
    assert "1 / 5" in page_text(out, 0)
    assert "5 / 5" in page_text(out, 4)
    skipped = page_numbers(sample_pdf, tmp_path / "s.pdf", template="Sayfa {n}", skip_first=True)
    assert "Sayfa" not in page_text(skipped, 0)
    assert "Sayfa 1" in page_text(skipped, 1)


def test_protect_and_unlock(tmp_path, sample_pdf):
    locked = protect(sample_pdf, tmp_path / "p.pdf", "pa55", allow_copy=False)
    assert is_encrypted(locked)
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(locked)
    with pikepdf.open(locked, password="pa55") as pdf:
        assert len(pdf.pages) == 5
    with pytest.raises(WrongPasswordError):
        unlock(locked, tmp_path / "u.pdf", "nope")
    opened = unlock(locked, tmp_path / "u.pdf", "pa55")
    assert not is_encrypted(opened)


def test_operations_explain_missing_password(tmp_path, encrypted_pdf):
    with pytest.raises(PasswordRequiredError):
        compress(encrypted_pdf, tmp_path / "x.pdf")


def test_set_and_strip_metadata(tmp_path, sample_pdf):
    assert read_metadata(sample_pdf)["title"] == "Sample Title"
    edited = set_metadata(sample_pdf, tmp_path / "m.pdf", {"title": "Yeni Başlık", "author": "", "keywords": "a, b"})
    meta = read_metadata(edited)
    assert meta["title"] == "Yeni Başlık"
    assert meta["author"] == ""
    assert meta["keywords"] == "a, b"
    clean = strip_metadata(edited, tmp_path / "clean.pdf")
    assert all(value == "" for value in read_metadata(clean).values())
    with pikepdf.open(clean) as pdf:
        assert "/Metadata" not in pdf.Root


def test_get_info(sample_pdf, second_pdf, encrypted_pdf):
    info = get_info(sample_pdf)
    assert info.pages == 5
    assert info.page_sizes == [("210 x 297 mm (A4)", 5)]
    assert info.metadata["title"] == "Sample Title"
    assert info.has_text and info.bookmarks == 5 and not info.encrypted
    assert get_info(second_pdf).page_sizes == [("297 x 210 mm (A4)", 3)]
    with pytest.raises(PasswordRequiredError):
        get_info(encrypted_pdf)
    assert get_info(encrypted_pdf, password="secret").encrypted
