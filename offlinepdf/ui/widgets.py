"""Reusable widgets: drop zone, file list, page thumbnail grid, small helpers."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from .. import i18n
from ..i18n import t
from . import icons, theme
from .worker import THUMB_POOL, ThumbnailJob, ThumbSignals

PATH_ROLE = Qt.UserRole
META_ROLE = Qt.UserRole + 1
INDEX_ROLE = Qt.UserRole + 2
LOCK_ROLE = Qt.UserRole + 3


# --------------------------------------------------------------------------- helpers


class IconBadge(QLabel):
    """A rounded square with a colored glyph, used on cards and page headers."""

    def __init__(self, name: str, color: str, size: int = 44, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setText(icons.glyph(name))
        self.setStyleSheet(
            f"background: {theme.rgba(color, 0.14)}; color: {color}; border-radius: {size // 4}px;"
            + icons.glyph_css(int(size * 0.46))
        )


def glyph_label(name: str, size: float = 12, color: str | None = None) -> QLabel:
    """A glyph icon as a label; ``size`` is in points (converted to pixels)."""
    label = QLabel(icons.glyph(name))
    css = "background: transparent;" + icons.glyph_css(int(size * 4 / 3))
    if color:
        css += f"color: {color};"
    label.setStyleSheet(css)
    return label


def open_path(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def reveal_in_folder(path: Path) -> None:
    path = Path(path)
    if os.name == "nt" and path.exists():
        import subprocess

        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        open_path(path if path.is_dir() else path.parent)


def placeholder_page(width: int, height: int) -> QPixmap:
    pm = QPixmap(width, height)
    pm.fill(QColor(theme.color("surface2")))
    painter = QPainter(pm)
    painter.setPen(QPen(QColor(theme.color("border_strong")), 1))
    for i, y in enumerate(range(int(height * 0.18), int(height * 0.8), max(6, height // 14))):
        line_w = width * (0.7 if i % 3 else 0.5)
        painter.drawLine(int(width * 0.15), y, int(width * 0.15 + line_w), y)
    painter.end()
    return pm


# --------------------------------------------------------------------------- drop zone


class DropZone(QFrame):
    """Big dashed area: drop files or click to browse."""

    files_dropped = Signal(list)

    def __init__(self, kind: str = "pdf", multi: bool = True, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.multi = multi
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 28)
        layout.setSpacing(6)
        layout.addStretch(1)
        icon = glyph_label("img2pdf" if kind == "image" else "file", 30, theme.color("accent"))
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)
        if kind == "image":
            title_text = t("common.drop_images")
        else:
            title_text = t("common.drop_pdf") if multi else t("common.drop_pdf_one")
        self.title = QLabel(title_text)
        self.title.setObjectName("DropTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        sub = QLabel(t("common.or_browse"))
        sub.setObjectName("Muted")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)
        layout.addStretch(1)

    def filter_string(self) -> str:
        if self.kind == "image":
            return "Images (*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp)"
        return "PDF (*.pdf)"

    def browse(self) -> None:
        if self.multi:
            files, _ = QFileDialog.getOpenFileNames(self, "", "", self.filter_string())
        else:
            file, _ = QFileDialog.getOpenFileName(self, "", "", self.filter_string())
            files = [file] if file else []
        if files:
            self.files_dropped.emit(files)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.browse()
        super().mouseReleaseEvent(event)

    def _set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, event) -> None:
        self._set_active(False)

    def dropEvent(self, event) -> None:
        self._set_active(False)
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            self.files_dropped.emit(files if self.multi else files[:1])
            event.acceptProposedAction()


# --------------------------------------------------------------------------- file list


@dataclass
class FileEntry:
    path: Path
    pages: int | None = None
    size: int = 0
    locked: bool = False
    password: str | None = None

    @property
    def name(self) -> str:
        return self.path.name

    def meta_text(self) -> str:
        parts = []
        if self.locked and not self.password:
            parts.append(t("common.locked"))
        elif self.pages is not None:
            parts.append(t("common.page_count_one") if self.pages == 1 else t("common.pages_count", n=self.pages))
        parts.append(i18n.human_size(self.size))
        return "  ·  ".join(parts)


class FileRowDelegate(QStyledItemDelegate):
    ROW_HEIGHT = 74

    def __init__(self, numbered: bool, parent=None):
        super().__init__(parent)
        self.numbered = numbered

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(2, 3, -2, -3)
        selected = bool(option.state & QStyle.State_Selected)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.fillPath(path, QColor(theme.color("accent_soft") if selected else theme.color("surface")))
        painter.setPen(QPen(QColor(theme.color("accent") if selected else theme.color("border")), 1))
        painter.drawPath(path)

        x = rect.left() + 12
        if self.numbered:
            badge = QRectF(x, rect.center().y() - 11, 22, 22)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.color("accent")))
            painter.drawEllipse(badge)
            painter.setPen(QColor(theme.color("on_accent")))
            font = QFont(painter.font())
            font.setPointSizeF(8.5)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(badge, Qt.AlignCenter, str(index.row() + 1))
            x += 32

        thumb = index.data(Qt.DecorationRole)
        thumb_rect = QRectF(x, rect.top() + 8, 44, rect.height() - 16)
        if isinstance(thumb, QPixmap) and not thumb.isNull():
            scaled = thumb.scaled(thumb_rect.size().toSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            target = QRectF(
                thumb_rect.center().x() - scaled.width() / 2,
                thumb_rect.center().y() - scaled.height() / 2,
                scaled.width(),
                scaled.height(),
            )
            painter.drawPixmap(target.toRect(), scaled)
            painter.setPen(QPen(QColor(theme.color("border_strong")), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(target)
        x += 58

        text_rect = QRectF(x, rect.top() + 12, rect.right() - x - 12, rect.height() - 24)
        name_font = QFont(option.font)
        name_font.setBold(True)
        name_font.setPointSizeF(10)
        painter.setFont(name_font)
        painter.setPen(QColor(theme.color("text")))
        metrics = painter.fontMetrics()
        name = metrics.elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideMiddle, int(text_rect.width()))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignTop, name)
        meta_font = QFont(option.font)
        meta_font.setPointSizeF(9)
        painter.setFont(meta_font)
        locked = bool(index.data(LOCK_ROLE))
        painter.setPen(QColor(theme.color("danger") if locked else theme.color("muted")))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignBottom, index.data(META_ROLE) or "")
        painter.restore()


class FileList(QListWidget):
    """Vertical list of files with thumbnails; optionally drag to reorder."""

    order_changed = Signal()

    def __init__(self, reorderable: bool = False, numbered: bool = False, parent=None):
        super().__init__(parent)
        self.setItemDelegate(FileRowDelegate(numbered, self))
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setSpacing(1)
        if reorderable:
            self.setDragDropMode(QAbstractItemView.InternalMove)
            self.setDefaultDropAction(Qt.MoveAction)
            self.model().rowsMoved.connect(lambda *_: self.order_changed.emit())

    def add_entry(self, entry: FileEntry) -> QListWidgetItem:
        item = QListWidgetItem(entry.name)
        item.setData(PATH_ROLE, str(entry.path))
        item.setData(META_ROLE, entry.meta_text())
        item.setData(LOCK_ROLE, entry.locked and not entry.password)
        item.setData(Qt.DecorationRole, placeholder_page(44, 58))
        item.setToolTip(str(entry.path))
        self.addItem(item)
        return item

    def paths(self) -> list[str]:
        return [self.item(i).data(PATH_ROLE) for i in range(self.count())]

    def set_thumbnail(self, path: str, image: QImage) -> None:
        for i in range(self.count()):
            item = self.item(i)
            if item.data(PATH_ROLE) == path:
                item.setData(Qt.DecorationRole, QPixmap.fromImage(image))

    def move_selected(self, delta: int) -> None:
        rows = sorted({self.row(item) for item in self.selectedItems()}, reverse=delta > 0)
        for row in rows:
            target = row + delta
            if 0 <= target < self.count():
                item = self.takeItem(row)
                self.insertItem(target, item)
                item.setSelected(True)
        self.order_changed.emit()


# --------------------------------------------------------------------------- page grid


class PageDelegate(QStyledItemDelegate):
    CELL = QSize(150, 200)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode  # "select" | "delete" | "reorder"

    def sizeHint(self, option, index) -> QSize:
        return self.CELL

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(option.rect).adjusted(6, 6, -6, -6)
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)
        accent = theme.color("danger") if self.mode == "delete" else theme.color("accent")

        card = QPainterPath()
        card.addRoundedRect(rect, 10, 10)
        if selected:
            fill = QColor(accent)
            fill.setAlpha(30)
            painter.fillPath(card, fill)
        elif hover:
            painter.fillPath(card, QColor(theme.color("surface2")))
        if selected or hover:
            painter.setPen(QPen(QColor(accent if selected else theme.color("border_strong")), 2 if selected else 1))
            painter.drawPath(card)

        area = QRectF(rect.left() + 10, rect.top() + 10, rect.width() - 20, rect.height() - 40)
        thumb = index.data(Qt.DecorationRole)
        if isinstance(thumb, QPixmap) and not thumb.isNull():
            size = thumb.size().scaled(area.size().toSize(), Qt.KeepAspectRatio)
            target = QRectF(
                area.center().x() - size.width() / 2,
                area.bottom() - size.height(),
                size.width(),
                size.height(),
            )
            shadow = target.translated(2, 3)
            painter.fillRect(shadow, QColor(theme.color("shadow")))
            painter.drawPixmap(target, thumb, QRectF(thumb.rect()))
            painter.setPen(QPen(QColor(theme.color("border_strong")), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(target)
            if selected and self.mode == "delete":
                painter.fillRect(target, QColor(220, 38, 38, 70))
                painter.setPen(QColor("#ffffff"))
                painter.setFont(icons.icon_font(20))
                painter.drawText(target, Qt.AlignCenter, icons.glyph("delete"))
            elif selected and self.mode == "select":
                mark = QRectF(target.right() - 26, target.top() + 6, 20, 20)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(accent))
                painter.drawEllipse(mark)
                painter.setPen(QColor("#ffffff"))
                painter.setFont(icons.icon_font(9))
                painter.drawText(mark, Qt.AlignCenter, icons.glyph("check"))

        label_rect = QRectF(rect.left(), rect.bottom() - 26, rect.width(), 22)
        font = QFont(option.font)
        font.setPointSizeF(9.5)
        font.setBold(selected)
        painter.setFont(font)
        painter.setPen(QColor(accent if selected else theme.color("muted")))
        original = index.data(INDEX_ROLE)
        label = str(original + 1)
        if self.mode == "reorder" and original != index.row():
            label = f"{index.row() + 1}  ·  ({original + 1})"
        painter.drawText(label_rect, Qt.AlignCenter, label)
        painter.restore()


class PageGrid(QListWidget):
    """Wrapping grid of page thumbnails for selecting or reordering pages."""

    selection_changed_pages = Signal(list)
    order_changed = Signal()

    def __init__(self, mode: str = "select", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setItemDelegate(PageDelegate(mode, self))
        self.setViewMode(QListWidget.ListMode)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.Adjust)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        if mode == "reorder":
            self.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self.setDragDropMode(QAbstractItemView.InternalMove)
            self.setDefaultDropAction(Qt.MoveAction)
            self.setDragEnabled(True)
            self.model().rowsMoved.connect(lambda *_: self._after_move())
        else:
            self.setSelectionMode(QAbstractItemView.MultiSelection)
            self.itemSelectionChanged.connect(
                lambda: self.selection_changed_pages.emit(self.selected_indices())
            )
        self._token = ""
        self._signals = ThumbSignals()
        self._signals.ready.connect(self._on_thumb)
        self._job: ThumbnailJob | None = None

    def _after_move(self) -> None:
        self.viewport().update()
        self.order_changed.emit()

    def load(self, path: str, pages: int, password: str | None = None) -> None:
        if self._job is not None:
            self._job.cancelled = True
        self.clear()
        placeholder = placeholder_page(110, 150)
        for index in range(pages):
            item = QListWidgetItem("")
            item.setData(INDEX_ROLE, index)
            item.setData(Qt.DecorationRole, placeholder)
            item.setSizeHint(PageDelegate.CELL)
            self.addItem(item)
        self._token = uuid.uuid4().hex
        self._job = ThumbnailJob(self._token, path, list(range(pages)), 260, password, self._signals)
        THUMB_POOL.start(self._job)

    def _on_thumb(self, token: str, index: int, image: QImage) -> None:
        if token != self._token:
            return
        pixmap = QPixmap.fromImage(image)
        for row in range(self.count()):
            item = self.item(row)
            if item.data(INDEX_ROLE) == index:
                item.setData(Qt.DecorationRole, pixmap)
                break

    def selected_indices(self) -> list[int]:
        return sorted(item.data(INDEX_ROLE) for item in self.selectedItems())

    def set_selected_indices(self, indices: list[int]) -> None:
        wanted = set(indices)
        self.blockSignals(True)
        for row in range(self.count()):
            item = self.item(row)
            item.setSelected(item.data(INDEX_ROLE) in wanted)
        self.blockSignals(False)
        self.viewport().update()
        self.selection_changed_pages.emit(self.selected_indices())

    def order(self) -> list[int]:
        return [self.item(row).data(INDEX_ROLE) for row in range(self.count())]

    def set_order(self, order: list[int]) -> None:
        items = {self.item(row).data(INDEX_ROLE): self.item(row) for row in range(self.count())}
        taken = {}
        while self.count():
            item = self.takeItem(0)
            taken[item.data(INDEX_ROLE)] = item
        for index in order:
            self.addItem(taken.get(index) or items[index])
        self.viewport().update()
        self.order_changed.emit()


# --------------------------------------------------------------------------- output row


class OutputRow(QWidget):
    """Where results are saved: next to the original, or a chosen folder."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title = QLabel(t("common.save_to"))
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(glyph_label("folder", 12, theme.color("muted")))
        self.label = QLabel()
        self.label.setObjectName("Muted")
        row.addWidget(self.label, 1)
        layout.addLayout(row)
        buttons = QHBoxLayout()
        self.change = QPushButton(t("common.change"))
        self.change.setObjectName("Link")
        self.change.setCursor(Qt.PointingHandCursor)
        self.change.clicked.connect(self.choose)
        self.reset = QPushButton(t("common.reset"))
        self.reset.setObjectName("Link")
        self.reset.setCursor(Qt.PointingHandCursor)
        self.reset.clicked.connect(lambda: self.set_folder(""))
        buttons.addWidget(self.change)
        buttons.addWidget(self.reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.set_folder(str(settings.value("output_dir", "") or ""))

    def folder(self) -> str:
        return self._folder

    def set_folder(self, folder: str) -> None:
        self._folder = folder if folder and os.path.isdir(folder) else ""
        self.settings.setValue("output_dir", self._folder)
        text = self._folder or t("common.same_folder")
        self.label.setText(self.label.fontMetrics().elidedText(text, Qt.ElideMiddle, 290))
        self.label.setToolTip(self._folder)
        self.reset.setVisible(bool(self._folder))

    def choose(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("common.save_to"), self._folder or "")
        if folder:
            self.set_folder(folder)

    def out_dir_for(self, source: str | Path) -> Path:
        return Path(self._folder) if self._folder else Path(source).parent
