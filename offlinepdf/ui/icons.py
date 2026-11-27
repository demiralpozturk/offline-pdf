"""Icons drawn from the Windows icon fonts, with a letter fallback elsewhere."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap

GLYPHS = {
    "merge": "",
    "split": "",
    "extract": "",
    "delete": "",
    "reorder": "",
    "rotate": "",
    "compress": "",
    "img2pdf": "",
    "pdf2img": "",
    "watermark": "",
    "numbers": "",
    "protect": "",
    "unlock": "",
    "metadata": "",
    "info": "",
    "back": "",
    "folder": "",
    "file": "",
    "sun": "",
    "moon": "",
    "language": "",
    "about": "",
    "shield": "",
    "check": "",
    "heart": "",
    "link": "",
    "add": "",
    "up": "",
    "down": "",
    "close": "",
    "search": "",
    "copy": "",
    "error": "",
}

FALLBACK = {key: key[:1].upper() for key in GLYPHS}

_family: str | None = None


def icon_family() -> str | None:
    """'Segoe Fluent Icons' (Win 11) or 'Segoe MDL2 Assets' (Win 10), else None."""
    global _family
    if _family is None:
        families = set(QFontDatabase.families())
        for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if name in families:
                _family = name
                break
        else:
            _family = ""
    return _family or None


def glyph(name: str) -> str:
    return GLYPHS.get(name, "") if icon_family() else FALLBACK.get(name, "?")


def icon_font(point_size: float) -> QFont:
    family = icon_family()
    font = QFont(family) if family else QFont()
    font.setPointSizeF(point_size)
    if not family:
        font.setBold(True)
    return font


def glyph_css(pixel_size: int) -> str:
    """Stylesheet fragment for glyph labels (stylesheets override QWidget.setFont)."""
    family = icon_family()
    if family:
        return f'font-family: "{family}"; font-size: {pixel_size}px; font-weight: normal;'
    return f"font-size: {pixel_size}px; font-weight: bold;"


def pixmap(name: str, size: int, color: str, dpr: float = 2.0) -> QPixmap:
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    painter.setPen(QColor(color))
    font = icon_font(size * 0.62)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, glyph(name))
    painter.end()
    return pm


def icon(name: str, color: str, size: int = 20) -> QIcon:
    return QIcon(pixmap(name, size, color))
