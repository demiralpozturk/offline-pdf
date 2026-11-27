"""Text watermarks and page numbers, drawn as vector overlays.

Overlays are built with reportlab using a Unicode TrueType font (so Turkish
and other non-Latin-1 text works) and stamped with pikepdf. Rotated pages are
handled so that text always appears upright to the reader.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pikepdf
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .document import Progress, open_pdf, report, save_pdf
from .pages import parse_selection

_FONT_NAME: str | None = None

_FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]


def font_name() -> str:
    """Register the first available Unicode font, falling back to Helvetica."""
    global _FONT_NAME
    if _FONT_NAME:
        return _FONT_NAME
    windir = os.environ.get("WINDIR")
    candidates = list(_FONT_CANDIDATES)
    if windir:
        candidates.insert(0, os.path.join(windir, "Fonts", "segoeui.ttf"))
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                pdfmetrics.registerFont(TTFont("OfflinePDFSans", candidate))
                _FONT_NAME = "OfflinePDFSans"
                return _FONT_NAME
            except Exception:
                continue
    _FONT_NAME = "Helvetica"
    return _FONT_NAME


def _visible_box(page: pikepdf.Page) -> list[float]:
    # pikepdf resolves inheritance and falls back to the MediaBox.
    return [float(v) for v in page.cropbox]


def _display_transform(rotation: int, width: float, height: float):
    """Matrix mapping reader-facing coordinates to the page's unrotated space."""
    rotation %= 360
    if rotation == 90:
        return (0, 1, -1, 0, width, 0)
    if rotation == 180:
        return (-1, 0, 0, -1, width, height)
    if rotation == 270:
        return (0, -1, 1, 0, 0, height)
    return (1, 0, 0, 1, 0, 0)


def _overlay_page(width: float, height: float, rotation: int, draw) -> bytes:
    """Build a one-page PDF of the page's unrotated size; ``draw`` gets upright coordinates."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height), pageCompression=1)
    pdf.transform(*_display_transform(rotation, width, height))
    display_w, display_h = (height, width) if rotation % 180 == 90 else (width, height)
    draw(pdf, display_w, display_h)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _stamp(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    draw_for_page,
    *,
    pages: str = "",
    under: bool = False,
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    with open_pdf(src, password) as pdf:
        count = len(pdf.pages)
        targets = parse_selection(pages, count) if pages.strip() else list(range(count))
        overlays: list[pikepdf.Pdf] = []
        try:
            for done, index in enumerate(targets):
                page = pdf.pages[index]
                x0, y0, x1, y1 = _visible_box(page)
                width, height = abs(x1 - x0), abs(y1 - y0)
                rotation = int(page.rotation or 0)
                drawer = draw_for_page(index, count)
                if drawer is None:
                    continue
                data = _overlay_page(width, height, rotation, drawer)
                overlay_pdf = pikepdf.open(io.BytesIO(data))
                overlays.append(overlay_pdf)
                rect = pikepdf.Rectangle(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                if under:
                    page.add_underlay(overlay_pdf.pages[0], rect)
                else:
                    page.add_overlay(overlay_pdf.pages[0], rect)
                report(progress, done + 1, len(targets))
            return save_pdf(pdf, dst)
        finally:
            for overlay_pdf in overlays:
                overlay_pdf.close()


def watermark(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    text: str,
    *,
    font_size: float = 48,
    color: str = "#d32f2f",
    opacity: float = 0.25,
    angle: float = 45,
    tiled: bool = False,
    under: bool = False,
    pages: str = "",
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    """Stamp ``text`` on pages, centered or tiled, at ``angle`` degrees."""
    text = (text or "").strip()
    if not text:
        raise ValueError("watermark text is empty")
    font = font_name()
    fill = HexColor(color)
    alpha = min(1.0, max(0.02, float(opacity)))

    def draw(pdf: canvas.Canvas, width: float, height: float) -> None:
        pdf.setFillColor(fill)
        pdf.setFillAlpha(alpha)
        pdf.setFont(font, font_size)
        text_width = pdfmetrics.stringWidth(text, font, font_size)
        if tiled:
            step_x = text_width + font_size * 2
            step_y = font_size * 4
            pdf.saveState()
            pdf.translate(width / 2, height / 2)
            pdf.rotate(angle)
            reach = (width ** 2 + height ** 2) ** 0.5
            y = -reach
            row = 0
            while y < reach:
                offset = (row % 2) * step_x / 2
                x = -reach - offset
                while x < reach:
                    pdf.drawString(x, y, text)
                    x += step_x
                y += step_y
                row += 1
            pdf.restoreState()
        else:
            pdf.saveState()
            pdf.translate(width / 2, height / 2)
            pdf.rotate(angle)
            pdf.drawString(-text_width / 2, -font_size / 3, text)
            pdf.restoreState()

    return _stamp(src, dst, lambda index, count: draw, pages=pages, under=under, password=password, progress=progress)


POSITIONS = (
    "bottom-center",
    "bottom-right",
    "bottom-left",
    "top-center",
    "top-right",
    "top-left",
)


def page_numbers(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    *,
    position: str = "bottom-center",
    template: str = "{n} / {total}",
    start: int = 1,
    font_size: float = 11,
    margin_mm: float = 12,
    color: str = "#333333",
    skip_first: bool = False,
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    """Write page numbers. ``template`` understands {n} and {total}."""
    if position not in POSITIONS:
        raise ValueError(f"unknown position: {position}")
    font = font_name()
    fill = HexColor(color)
    margin = float(margin_mm) * 72 / 25.4

    def for_page(index: int, count: int):
        if skip_first and index == 0:
            return None
        numbered_total = count - (1 if skip_first else 0)
        number = start + index - (1 if skip_first else 0)
        label = template.replace("{n}", str(number)).replace("{total}", str(start + numbered_total - 1))

        def draw(pdf: canvas.Canvas, width: float, height: float) -> None:
            pdf.setFillColor(fill)
            pdf.setFont(font, font_size)
            vertical, horizontal = position.split("-")
            y = margin if vertical == "bottom" else height - margin - font_size
            if horizontal == "center":
                pdf.drawCentredString(width / 2, y, label)
            elif horizontal == "right":
                pdf.drawRightString(width - margin, y, label)
            else:
                pdf.drawString(margin, y, label)

        return draw

    return _stamp(src, dst, for_page, password=password, progress=progress)
