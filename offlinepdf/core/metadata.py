"""Read, edit and remove document metadata; summarize a PDF."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pikepdf
from pikepdf import Name

from .document import Progress, open_pdf, report, save_pdf
from .render import open_document, PDFIUM_LOCK

FIELDS = ("title", "author", "subject", "keywords", "creator", "producer")
_KEYS = {name: Name("/" + name.capitalize()) for name in FIELDS}


def _text(value) -> str:
    try:
        return str(value).strip()
    except Exception:
        return ""


def read_metadata(src: str | os.PathLike, password: str | None = None) -> dict[str, str]:
    with open_pdf(src, password) as pdf:
        info = pdf.docinfo
        return {name: _text(info.get(key, "")) for name, key in _KEYS.items()}


def set_metadata(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    values: dict[str, str],
    *,
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    """Set the given fields; an empty string removes that field."""
    with open_pdf(src, password) as pdf:
        info = pdf.docinfo
        for name, value in values.items():
            if name not in _KEYS:
                continue
            key = _KEYS[name]
            value = (value or "").strip()
            if value:
                info[key] = value
            elif key in info:
                del info[key]
        with warnings.catch_warnings():
            # Some docinfo keys (e.g. /Trapped) have no XMP equivalent; that is fine.
            warnings.simplefilter("ignore", UserWarning)
            with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
                meta.load_from_docinfo(pdf.docinfo, delete_missing=True)
        out = save_pdf(pdf, dst)
    report(progress, 1, 1)
    return out


def strip_metadata(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    *,
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    """Remove the document info dictionary, XMP metadata and page piece info."""
    with open_pdf(src, password) as pdf:
        if "/Info" in pdf.trailer:
            del pdf.trailer["/Info"]
        for key in ("/Metadata", "/PieceInfo"):
            if key in pdf.Root:
                del pdf.Root[key]
        for page in pdf.pages:
            for key in ("/Metadata", "/PieceInfo"):
                if key in page.obj:
                    del page.obj[key]
        out = save_pdf(pdf, dst)
    report(progress, 1, 1)
    return out


@dataclass
class PdfInfo:
    path: Path
    file_size: int
    pages: int
    version: str
    encrypted: bool
    page_sizes: list[tuple[str, int]] = field(default_factory=list)  # ("210 x 297 mm (A4)", count)
    metadata: dict[str, str] = field(default_factory=dict)
    created: str = ""
    modified: str = ""
    images: int = 0
    has_text: bool = False
    bookmarks: int = 0
    attachments: int = 0
    has_forms: bool = False
    linearized: bool = False


_NAMED_SIZES = {
    (210, 297): "A4",
    (148, 210): "A5",
    (297, 420): "A3",
    (216, 279): "Letter",
    (216, 356): "Legal",
}


def _size_label(width_pt: float, height_pt: float) -> str:
    w_mm, h_mm = round(width_pt * 25.4 / 72), round(height_pt * 25.4 / 72)
    short, long_ = sorted((w_mm, h_mm))
    name = ""
    for (a, b), label in _NAMED_SIZES.items():
        if abs(short - a) <= 2 and abs(long_ - b) <= 2:
            name = f" ({label})"
            break
    return f"{w_mm} x {h_mm} mm{name}"


def _pdf_date(value) -> str:
    text = _text(value)
    if text.startswith("D:"):
        text = text[2:]
    digits = "".join(ch for ch in text[:14] if ch.isdigit())
    for fmt, size in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12), ("%Y%m%d", 8)):
        if len(digits) >= size:
            try:
                return datetime.strptime(digits[:size], fmt).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                continue
    return text


def get_info(src: str | os.PathLike, password: str | None = None) -> PdfInfo:
    src = Path(src)
    with open_pdf(src, password) as pdf:
        sizes: dict[str, int] = {}
        seen_images: set[tuple[int, int]] = set()
        for page in pdf.pages:
            x0, y0, x1, y1 = (float(v) for v in page.cropbox)
            width, height = abs(x1 - x0), abs(y1 - y0)
            if int(page.rotation or 0) % 180 == 90:
                width, height = height, width
            label = _size_label(width, height)
            sizes[label] = sizes.get(label, 0) + 1
            try:
                for _, stream in page.get_images().items():
                    seen_images.add(stream.objgen)
            except Exception:
                pass
        info = pdf.docinfo
        try:
            with pdf.open_outline() as outline:
                bookmarks = _count_outline(outline.root)
        except Exception:
            bookmarks = 0
        attachments = len(pdf.attachments) if hasattr(pdf, "attachments") else 0
        result = PdfInfo(
            path=src,
            file_size=src.stat().st_size,
            pages=len(pdf.pages),
            version=str(pdf.pdf_version),
            encrypted=bool(pdf.is_encrypted),
            page_sizes=sorted(sizes.items(), key=lambda item: -item[1]),
            metadata={name: _text(info.get(key, "")) for name, key in _KEYS.items()},
            created=_pdf_date(info.get("/CreationDate", "")),
            modified=_pdf_date(info.get("/ModDate", "")),
            images=len(seen_images),
            bookmarks=bookmarks,
            attachments=attachments,
            has_forms="/AcroForm" in pdf.Root and len(pdf.Root.AcroForm.get("/Fields", [])) > 0,
            linearized=bool(pdf.is_linearized),
        )
    result.has_text = _has_text(src, password, min(result.pages, 3))
    return result


def _count_outline(items) -> int:
    total = 0
    for item in items:
        total += 1 + _count_outline(item.children)
    return total


def _has_text(src: Path, password: str | None, pages: int) -> bool:
    try:
        with open_document(src, password) as doc:
            with PDFIUM_LOCK:
                for index in range(pages):
                    page = doc[index]
                    try:
                        textpage = page.get_textpage()
                        try:
                            if textpage.count_chars() > 0:
                                return True
                        finally:
                            textpage.close()
                    finally:
                        page.close()
    except Exception:
        return False
    return False
