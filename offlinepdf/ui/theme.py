"""Light and dark themes as one Qt stylesheet template."""

from __future__ import annotations

PALETTES = {
    "light": {
        "bg": "#f4f6fb",
        "surface": "#ffffff",
        "surface2": "#f8f9fd",
        "border": "#e2e6ef",
        "border_strong": "#cfd5e3",
        "text": "#161b26",
        "muted": "#5d6678",
        "accent": "#4f46e5",
        "accent_hover": "#4338ca",
        "accent_soft": "#eef0ff",
        "on_accent": "#ffffff",
        "chip_bg": "#e6f6ee",
        "chip_text": "#11784a",
        "danger": "#dc2626",
        "danger_soft": "#fde8e8",
        "success": "#16a34a",
        "success_soft": "#e7f7ed",
        "input": "#ffffff",
        "shadow": "#d9deea",
        "page": "#ffffff",
    },
    "dark": {
        "bg": "#0e1117",
        "surface": "#161b24",
        "surface2": "#1b212c",
        "border": "#272e3c",
        "border_strong": "#36405a",
        "text": "#e8ebf2",
        "muted": "#98a1b3",
        "accent": "#8b84ff",
        "accent_hover": "#9f99ff",
        "accent_soft": "#23264a",
        "on_accent": "#0e1117",
        "chip_bg": "#12291e",
        "chip_text": "#5fe3a0",
        "danger": "#f87171",
        "danger_soft": "#3a1d22",
        "success": "#4ade80",
        "success_soft": "#13291c",
        "input": "#11151d",
        "shadow": "#07090d",
        "page": "#f3f4f7",
    },
}

CATEGORY_COLORS = {
    "organize": "#3b82f6",
    "optimize": "#10b981",
    "convert": "#f59e0b",
    "edit": "#a855f7",
    "security": "#ef4444",
}

_mode = "light"


def set_mode(mode: str) -> None:
    global _mode
    _mode = mode if mode in PALETTES else "light"


def mode() -> str:
    return _mode


def color(name: str) -> str:
    return PALETTES[_mode][name]


def rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def _indicator_images() -> dict[str, str]:
    """Draw small PNGs (check mark, chevrons) that Qt stylesheets can reference."""
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

    from .. import __version__

    folder = Path(tempfile.gettempdir()) / f"OfflinePDF-ui-{__version__}" / _mode
    folder.mkdir(parents=True, exist_ok=True)
    muted = PALETTES[_mode]["muted"]
    on_accent = PALETTES[_mode]["on_accent"]

    def draw(name: str, points, color: str, width: float) -> str:
        target = folder / f"{name}.png"
        if not target.exists():
            pixmap = QPixmap(48, 48)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(color), width)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath(QPointF(*points[0]))
            for point in points[1:]:
                path.lineTo(QPointF(*point))
            painter.drawPath(path)
            painter.end()
            pixmap.save(str(target))
        return target.as_posix()

    return {
        "check": draw("check", [(11, 25), (20, 34), (37, 15)], on_accent, 6),
        "down": draw("down", [(12, 18), (24, 30), (36, 18)], muted, 5),
        "up": draw("up", [(12, 30), (24, 18), (36, 30)], muted, 5),
    }


def stylesheet() -> str:
    p = PALETTES[_mode]
    img = _indicator_images()
    return f"""
* {{ font-family: "Segoe UI", "Segoe UI Variable", "Inter", "Helvetica Neue", Arial, sans-serif; }}
QMainWindow, QWidget#Root {{ background: {p['bg']}; }}
QWidget {{ color: {p['text']}; font-size: 10pt; }}
QToolTip {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border']}; padding: 6px; }}

#Header {{ background: {p['surface']}; border-bottom: 1px solid {p['border']}; }}
#AppName {{ font-size: 15pt; font-weight: 700; }}
#Chip {{ background: {p['chip_bg']}; color: {p['chip_text']}; border-radius: 11px; padding: 3px 10px; font-weight: 600; font-size: 9pt; }}

#HeroTitle {{ font-size: 26pt; font-weight: 800; }}
#HeroSub {{ font-size: 12pt; color: {p['muted']}; }}
#SectionTitle {{ font-size: 10pt; font-weight: 700; color: {p['muted']}; letter-spacing: 1px; }}
#Muted, QLabel[muted="true"] {{ color: {p['muted']}; }}
#PageTitle {{ font-size: 19pt; font-weight: 800; }}
#PageDesc {{ color: {p['muted']}; font-size: 11pt; }}

#Card {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 14px; }}
#Card:hover {{ border: 1px solid {p['accent']}; background: {p['surface2']}; }}
#CardTitle {{ font-size: 11.5pt; font-weight: 700; }}
#CardDesc {{ color: {p['muted']}; font-size: 9.5pt; }}

#Panel {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 14px; }}
#PanelTitle {{ font-weight: 700; font-size: 11pt; }}

#DropZone {{ background: {p['surface2']}; border: 2px dashed {p['border_strong']}; border-radius: 14px; }}
#DropZone[active="true"] {{ border-color: {p['accent']}; background: {p['accent_soft']}; }}
#DropTitle {{ font-size: 12.5pt; font-weight: 700; }}

#ResultCard {{ background: {p['success_soft']}; border: 1px solid {p['success']}; border-radius: 12px; }}
#ErrorCard {{ background: {p['danger_soft']}; border: 1px solid {p['danger']}; border-radius: 12px; }}

QPushButton {{
    background: {p['surface']}; border: 1px solid {p['border_strong']}; border-radius: 9px;
    padding: 7px 14px; font-weight: 600;
}}
QPushButton:hover {{ border-color: {p['accent']}; color: {p['accent']}; }}
QPushButton:disabled {{ color: {p['muted']}; border-color: {p['border']}; }}
QPushButton#Primary {{
    background: {p['accent']}; color: {p['on_accent']}; border: none; border-radius: 11px;
    padding: 12px 18px; font-size: 11.5pt; font-weight: 700;
}}
QPushButton#Primary:hover {{ background: {p['accent_hover']}; color: {p['on_accent']}; }}
QPushButton#Primary:disabled {{ background: {p['border_strong']}; color: {p['surface']}; }}
QPushButton#Ghost, QToolButton#Ghost {{ background: transparent; border: none; padding: 6px 10px; color: {p['muted']}; font-weight: 600; }}
QPushButton#Ghost:hover, QToolButton#Ghost:hover {{ color: {p['accent']}; background: {p['accent_soft']}; border-radius: 8px; }}
QToolButton#IconButton {{ background: transparent; border: 1px solid transparent; border-radius: 9px; padding: 4px; }}
QToolButton#IconButton:hover {{ background: {p['accent_soft']}; border-color: {p['border']}; }}
QPushButton#Link {{ background: transparent; border: none; color: {p['accent']}; padding: 2px 4px; font-weight: 600; }}
QPushButton#Link:hover {{ text-decoration: underline; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {p['input']}; border: 1px solid {p['border_strong']}; border-radius: 8px; padding: 6px 8px;
    selection-background-color: {p['accent']}; selection-color: {p['on_accent']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {p['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {p['surface']}; border: 1px solid {p['border']}; selection-background-color: {p['accent_soft']}; selection-color: {p['text']}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QCheckBox::indicator {{ border: 1px solid {p['border_strong']}; border-radius: 4px; background: {p['input']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; border-color: {p['accent']}; image: url("{img['check']}"); }}
QRadioButton::indicator {{ border: 1px solid {p['border_strong']}; border-radius: 9px; background: {p['input']}; }}
QRadioButton::indicator:checked {{
    border: 1px solid {p['accent']};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 {p['accent']}, stop:0.45 {p['accent']}, stop:0.55 {p['input']}, stop:1 {p['input']});
}}
QComboBox::down-arrow {{ image: url("{img['down']}"); width: 12px; height: 12px; }}
QSpinBox, QDoubleSpinBox {{ padding-right: 24px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; width: 22px; border: none; background: transparent;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{img['up']}"); width: 10px; height: 10px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{img['down']}"); width: 10px; height: 10px; }}
QSlider::groove:horizontal {{ height: 6px; background: {p['border']}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {p['accent']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {p['accent']}; width: 16px; margin: -5px 0; border-radius: 8px; }}

QProgressBar {{ background: {p['border']}; border: none; border-radius: 5px; height: 10px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {p['accent']}; border-radius: 5px; }}

QListWidget {{ background: transparent; border: none; outline: none; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border_strong']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['border_strong']}; border-radius: 4px; min-width: 30px; }}

#Footer {{ color: {p['muted']}; font-size: 9pt; }}
QDialog {{ background: {p['bg']}; }}
#InfoKey {{ color: {p['muted']}; }}
#InfoValue {{ font-weight: 600; }}
"""
