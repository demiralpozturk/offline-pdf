"""The 15 tools: their options UI and how they call the core.

Each tool has two halves:
  collect(page)  runs on the UI thread and reads the option widgets
  execute(...)   runs on a worker thread and only calls offlinepdf.core
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import core, i18n
from ..core.document import unique_path
from ..i18n import human_size, t
from . import theme


class UserError(Exception):
    """A validation message to show next to the Start button."""


@dataclass
class Result:
    outputs: list[Path] = field(default_factory=list)
    message: str = ""


class Context:
    def __init__(self, out_dir_for: Callable[[str | Path], Path], progress: Callable[[int, int], None]):
        self.out_dir_for = out_dir_for
        self._progress = progress

    def progress(self, done: int, total: int) -> None:
        self._progress(int(done), int(max(total, 1)))

    def file_progress(self, index: int, count: int):
        """Progress callback for file ``index`` of ``count`` mapped onto 0..1000."""

        def callback(done: int, total: int) -> None:
            fraction = (index + (done / max(total, 1))) / max(count, 1)
            self._progress(int(fraction * 1000), 1000)

        return callback


# --------------------------------------------------------------------------- form helpers


def form() -> tuple[QWidget, QVBoxLayout]:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    return widget, layout


def labeled(layout: QVBoxLayout, text: str, widget: QWidget, hint: str = "") -> QWidget:
    box = QVBoxLayout()
    box.setSpacing(4)
    label = QLabel(text)
    label.setStyleSheet("font-weight: 600;")
    box.addWidget(label)
    box.addWidget(widget)
    if hint:
        hint_label = QLabel(hint)
        hint_label.setObjectName("Muted")
        hint_label.setWordWrap(True)
        box.addWidget(hint_label)
    layout.addLayout(box)
    return widget


def note(layout: QVBoxLayout, text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(True)
    layout.addWidget(label)
    return label


def radio_group(layout: QVBoxLayout, title: str, options: list[tuple[str, str]], default: str) -> QButtonGroup:
    label = QLabel(title)
    label.setStyleSheet("font-weight: 600;")
    layout.addWidget(label)
    group = QButtonGroup(layout.parentWidget())
    for value, text in options:
        button = QRadioButton(text)
        button.setProperty("value", value)
        button.setChecked(value == default)
        group.addButton(button)
        layout.addWidget(button)
    return group


def group_value(group: QButtonGroup) -> str:
    button = group.checkedButton()
    return button.property("value") if button else ""


def spin(minimum: int, maximum: int, value: int, suffix: str = "") -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    if suffix:
        box.setSuffix(suffix)
    return box


def password_edit() -> QLineEdit:
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.Password)
    return edit


# --------------------------------------------------------------------------- base


class Tool:
    id = ""
    icon = ""
    category = ""
    inputs = "pdf"  # "pdf" | "image"
    multi = True  # accepts several files (processed one by one unless merged)
    min_files = 1
    reorderable = False  # file list can be dragged
    numbered = False
    page_mode: str | None = None  # "select" | "delete" | "reorder"
    runnable = True
    prompt_passwords = True

    def title(self) -> str:
        return t(f"tool.{self.id}.title")

    def desc(self) -> str:
        return t(f"tool.{self.id}.desc")

    def build_options(self, page) -> QWidget | None:
        return None

    def on_files_changed(self, page) -> None:
        pass

    def on_pages_selected(self, page, indices: list[int]) -> None:
        pass

    def collect(self, page) -> dict:
        return {}

    def execute(self, entries, values: dict, ctx: Context) -> Result:
        raise NotImplementedError

    # Shared batch runner for "one output per input" tools.
    def batch(self, entries, ctx: Context, suffix: str, fn) -> Result:
        outputs = []
        for i, entry in enumerate(entries):
            dst = unique_path(ctx.out_dir_for(entry.path), entry.path.stem, suffix)
            outputs.append(fn(entry, dst, ctx.file_progress(i, len(entries))))
        return Result(outputs)


# --------------------------------------------------------------------------- organize


class MergeTool(Tool):
    id, icon, category = "merge", "merge", "organize"
    min_files = 2
    reorderable = True
    numbered = True

    def build_options(self, page):
        widget, layout = form()
        self.bookmarks = QCheckBox(t("merge.bookmarks"))
        self.bookmarks.setChecked(True)
        self.keep = QCheckBox(t("merge.keep_outlines"))
        self.keep.setChecked(True)
        layout.addWidget(self.bookmarks)
        layout.addWidget(self.keep)
        self.name = labeled(layout, t("common.file_name"), QLineEdit(t("merge.output_name")))
        return widget

    def collect(self, page):
        name = self.name.text().strip() or t("merge.output_name")
        if name.lower().endswith(".pdf"):
            name = name[:-4]
        return {"bookmarks": self.bookmarks.isChecked(), "keep": self.keep.isChecked(), "name": name}

    def execute(self, entries, values, ctx):
        dst = unique_path(ctx.out_dir_for(entries[0].path), values["name"])
        passwords = {str(e.path): e.password for e in entries if e.password}
        core.merge(
            [e.path for e in entries],
            dst,
            bookmarks=values["bookmarks"],
            keep_outlines=values["keep"],
            passwords=passwords,
            progress=ctx.progress,
        )
        return Result([dst])


class SplitTool(Tool):
    id, icon, category = "split", "split", "organize"

    def build_options(self, page):
        widget, layout = form()
        self.mode = radio_group(
            layout,
            t("split.mode"),
            [("each", t("split.each")), ("every", t("split.every")), ("ranges", t("split.ranges"))],
            "each",
        )
        self.every = labeled(layout, t("split.every_n"), spin(1, 100000, 2))
        self.ranges = labeled(layout, t("split.ranges_label"), QLineEdit(), t("split.ranges_hint"))
        self.ranges.setPlaceholderText(t("split.ranges_hint"))
        self.mode.buttonToggled.connect(lambda *_: self._sync())
        self._sync()
        return widget

    def _sync(self):
        mode = group_value(self.mode)
        self.every.setEnabled(mode == "every")
        self.ranges.setEnabled(mode == "ranges")

    def collect(self, page):
        mode = group_value(self.mode)
        if mode == "ranges" and not self.ranges.text().strip():
            raise UserError(t("error.invalid_range", spec=""))
        return {"mode": mode, "every": self.every.value(), "ranges": self.ranges.text()}

    def execute(self, entries, values, ctx):
        outputs = []
        for i, entry in enumerate(entries):
            folder = ctx.out_dir_for(entry.path) / f"{entry.path.stem}_split"
            outputs += core.split(
                entry.path,
                folder,
                mode=values["mode"],
                every=values["every"],
                ranges=values["ranges"],
                password=entry.password,
                progress=ctx.file_progress(i, len(entries)),
            )
        return Result(outputs)


class _PageSelectTool(Tool):
    multi = False
    page_mode = "select"
    suffix = "_extract"

    def build_options(self, page):
        widget, layout = form()
        note(layout, t("common.click_to_select"))
        self.pages = labeled(layout, t("common.pages"), QLineEdit())
        self.pages.setPlaceholderText(t("common.pages_hint"))
        self.pages.textEdited.connect(lambda text: self._typed(page, text))
        self.count_label = note(layout, "")
        return widget

    def _typed(self, page, text):
        if page.grid is None:
            return
        try:
            indices = core.parse_selection(text, page.grid.count()) if text.strip() else []
        except core.InvalidRangeError:
            return
        page.grid.set_selected_indices(indices)

    def on_pages_selected(self, page, indices):
        if not self.pages.hasFocus():
            self.pages.setText(core.format_selection(indices))
        total = page.grid.count() if page.grid is not None else 0
        self.count_label.setText(t("common.selected", n=len(indices), total=total) if total else "")

    def collect(self, page):
        spec = self.pages.text().strip()
        if not spec:
            raise UserError(t("extract.none"))
        return {"pages": spec}


class ExtractTool(_PageSelectTool):
    id, icon, category = "extract", "extract", "organize"

    def execute(self, entries, values, ctx):
        entry = entries[0]
        dst = unique_path(ctx.out_dir_for(entry.path), entry.path.stem, "_extract")
        core.extract(entry.path, dst, values["pages"], password=entry.password, progress=ctx.progress)
        return Result([dst])


class DeleteTool(_PageSelectTool):
    id, icon, category = "delete", "delete", "organize"
    page_mode = "delete"

    def collect(self, page):
        values = super().collect(page)
        total = page.grid.count() if page.grid is not None else 0
        try:
            if total and len(core.parse_selection(values["pages"], total)) >= total:
                raise UserError(t("delete.none_left"))
        except core.InvalidRangeError:
            pass
        return values

    def execute(self, entries, values, ctx):
        entry = entries[0]
        dst = unique_path(ctx.out_dir_for(entry.path), entry.path.stem, "_edited")
        core.delete(entry.path, dst, values["pages"], password=entry.password, progress=ctx.progress)
        return Result([dst])


class ReorderTool(Tool):
    id, icon, category = "reorder", "reorder", "organize"
    multi = False
    page_mode = "reorder"

    def build_options(self, page):
        widget, layout = form()
        note(layout, t("common.drag_to_reorder"))
        row = QHBoxLayout()
        reverse = QPushButton(t("common.reverse"))
        reverse.clicked.connect(lambda: page.grid and page.grid.set_order(list(reversed(page.grid.order()))))
        reset = QPushButton(t("common.reset_order"))
        reset.clicked.connect(lambda: page.grid and page.grid.set_order(sorted(page.grid.order())))
        row.addWidget(reverse)
        row.addWidget(reset)
        row.addStretch(1)
        layout.addLayout(row)
        return widget

    def collect(self, page):
        if page.grid is None or page.grid.count() == 0:
            raise UserError(t("common.add_files_first"))
        return {"order": page.grid.order()}

    def execute(self, entries, values, ctx):
        entry = entries[0]
        dst = unique_path(ctx.out_dir_for(entry.path), entry.path.stem, "_reordered")
        core.reorder(entry.path, dst, values["order"], password=entry.password, progress=ctx.progress)
        return Result([dst])


class RotateTool(Tool):
    id, icon, category = "rotate", "rotate", "organize"

    def build_options(self, page):
        widget, layout = form()
        self.angle = radio_group(
            layout,
            t("rotate.angle"),
            [("90", t("rotate.90")), ("180", t("rotate.180")), ("270", t("rotate.270"))],
            "90",
        )
        self.pages = labeled(layout, t("common.pages"), QLineEdit(), t("common.pages_all_hint"))
        self.pages.setPlaceholderText(t("common.pages_hint"))
        return widget

    def collect(self, page):
        return {"angle": int(group_value(self.angle) or 90), "pages": self.pages.text()}

    def execute(self, entries, values, ctx):
        return self.batch(
            entries,
            ctx,
            "_rotated",
            lambda e, dst, progress: core.rotate(
                e.path, dst, values["angle"], pages=values["pages"], password=e.password, progress=progress
            ),
        )


# --------------------------------------------------------------------------- optimize / convert


class CompressTool(Tool):
    id, icon, category = "compress", "compress", "optimize"

    def build_options(self, page):
        widget, layout = form()
        self.level = radio_group(
            layout,
            t("compress.level"),
            [("medium", t("compress.medium")), ("high", t("compress.high")), ("low", t("compress.low"))],
            "medium",
        )
        return widget

    def collect(self, page):
        return {"level": group_value(self.level) or "medium"}

    def execute(self, entries, values, ctx):
        outputs, before, after = [], 0, 0
        for i, entry in enumerate(entries):
            dst = unique_path(ctx.out_dir_for(entry.path), entry.path.stem, "_compressed")
            result = core.compress(
                entry.path, dst, level=values["level"], password=entry.password, progress=ctx.file_progress(i, len(entries))
            )
            outputs.append(result.path)
            before += result.original_size
            after += result.new_size
        if after >= before:
            message = t("compress.no_gain")
        else:
            percent = round((1 - after / before) * 100)
            message = t("compress.result", before=human_size(before), after=human_size(after), percent=percent)
        return Result(outputs, message)


class ImagesToPdfTool(Tool):
    id, icon, category = "img2pdf", "img2pdf", "convert"
    inputs = "image"
    reorderable = True
    numbered = True

    def build_options(self, page):
        widget, layout = form()
        self.size = QComboBox()
        for value in ("fit", "a4", "letter"):
            self.size.addItem(t(f"img2pdf.{value}"), value)
        labeled(layout, t("img2pdf.page_size"), self.size)
        self.margin = labeled(layout, t("img2pdf.margin"), spin(0, 50, 0, " mm"))
        self.size.currentIndexChanged.connect(
            lambda *_: self.margin.setValue(10 if self.size.currentData() != "fit" and self.margin.value() == 0 else self.margin.value())
        )
        self.name = labeled(layout, t("common.file_name"), QLineEdit(t("img2pdf.output_name")))
        return widget

    def collect(self, page):
        name = self.name.text().strip() or t("img2pdf.output_name")
        if name.lower().endswith(".pdf"):
            name = name[:-4]
        return {"size": self.size.currentData(), "margin": self.margin.value(), "name": name}

    def execute(self, entries, values, ctx):
        dst = unique_path(ctx.out_dir_for(entries[0].path), values["name"])
        core.images_to_pdf(
            [e.path for e in entries], dst, page_size=values["size"], margin_mm=values["margin"], progress=ctx.progress
        )
        return Result([dst])


class PdfToImagesTool(Tool):
    id, icon, category = "pdf2img", "pdf2img", "convert"

    def build_options(self, page):
        widget, layout = form()
        self.fmt = QComboBox()
        self.fmt.addItem("PNG", "png")
        self.fmt.addItem("JPG", "jpg")
        labeled(layout, t("pdf2img.format"), self.fmt)
        self.dpi = QComboBox()
        for dpi in (72, 96, 150, 200, 300, 600):
            self.dpi.addItem(f"{dpi} DPI", dpi)
        self.dpi.setCurrentIndex(2)
        labeled(layout, t("pdf2img.dpi"), self.dpi)
        self.quality = labeled(layout, t("pdf2img.quality"), spin(40, 100, 90, " %"))
        self.pages = labeled(layout, t("common.pages"), QLineEdit(), t("common.pages_all_hint"))
        self.pages.setPlaceholderText(t("common.pages_hint"))
        self.fmt.currentIndexChanged.connect(lambda *_: self.quality.setEnabled(self.fmt.currentData() == "jpg"))
        self.quality.setEnabled(False)
        return widget

    def collect(self, page):
        return {
            "fmt": self.fmt.currentData(),
            "dpi": int(self.dpi.currentData()),
            "quality": self.quality.value(),
            "pages": self.pages.text(),
        }

    def execute(self, entries, values, ctx):
        outputs = []
        for i, entry in enumerate(entries):
            folder = ctx.out_dir_for(entry.path) / f"{entry.path.stem}_images"
            outputs += core.pdf_to_images(
                entry.path,
                folder,
                fmt=values["fmt"],
                dpi=values["dpi"],
                quality=values["quality"],
                pages=values["pages"],
                password=entry.password,
                progress=ctx.file_progress(i, len(entries)),
            )
        return Result(outputs)


# --------------------------------------------------------------------------- edit


class WatermarkPreview(QWidget):
    """Approximate live preview of the watermark on the first page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.base: QPixmap | None = None
        self.page_width_pt = 595.0
        self.options: dict = {}

    def set_base(self, pixmap: QPixmap | None, page_width_pt: float) -> None:
        self.base = pixmap
        self.page_width_pt = page_width_pt or 595.0
        self.update()

    def set_options(self, **options) -> None:
        self.options = options
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        if self.base is None or self.base.isNull():
            painter.fillRect(area, QColor(theme.color("surface2")))
            painter.end()
            return
        size = self.base.size().scaled(area.size().toSize(), Qt.KeepAspectRatio)
        target = QRectF(area.center().x() - size.width() / 2, area.center().y() - size.height() / 2, size.width(), size.height())
        painter.fillRect(target.translated(2, 3), QColor(theme.color("shadow")))
        painter.drawPixmap(target, self.base, QRectF(self.base.rect()))
        painter.setClipRect(target)
        text = self.options.get("text") or ""
        if text:
            scale = target.width() / self.page_width_pt
            font = QFont("Segoe UI")
            font.setPixelSize(max(4, int(self.options.get("font_size", 48) * scale)))
            painter.setFont(font)
            color = QColor(self.options.get("color", "#d32f2f"))
            color.setAlphaF(max(0.02, min(1.0, self.options.get("opacity", 0.25))))
            painter.setPen(color)
            painter.translate(target.center())
            painter.rotate(-self.options.get("angle", 45))
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(text)
            if self.options.get("tiled"):
                step_x = width + font.pixelSize() * 2
                step_y = font.pixelSize() * 4
                reach = (target.width() ** 2 + target.height() ** 2) ** 0.5
                y, row = -reach, 0
                while y < reach:
                    x = -reach - (row % 2) * step_x / 2
                    while x < reach:
                        painter.drawText(int(x), int(y), text)
                        x += step_x
                    y += step_y
                    row += 1
            else:
                painter.drawText(int(-width / 2), int(metrics.ascent() / 3), text)
        painter.end()


class WatermarkTool(Tool):
    id, icon, category = "watermark", "watermark", "edit"

    def build_options(self, page):
        widget, layout = form()
        self.preview = WatermarkPreview()
        layout.addWidget(self.preview)
        self.text = labeled(layout, t("watermark.text"), QLineEdit(t("watermark.default")))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        self.size = spin(6, 300, 60)
        self.angle = spin(-90, 90, 45, "°")
        for col, (label, box) in enumerate(((t("watermark.font_size"), self.size), (t("watermark.angle"), self.angle))):
            title = QLabel(label)
            title.setStyleSheet("font-weight: 600;")
            grid.addWidget(title, 0, col)
            grid.addWidget(box, 1, col)
        layout.addLayout(grid)
        self.color = "#d32f2f"
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self._pick_color)
        labeled(layout, t("watermark.color"), self.color_button)
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(5, 100)
        self.opacity.setValue(30)
        labeled(layout, t("watermark.opacity"), self.opacity)
        self.tiled = QCheckBox(t("watermark.tiled"))
        self.under = QCheckBox(t("watermark.under"))
        layout.addWidget(self.tiled)
        layout.addWidget(self.under)
        self.pages = labeled(layout, t("common.pages"), QLineEdit(), t("common.pages_all_hint"))
        self.pages.setPlaceholderText(t("common.pages_hint"))
        for signal in (
            self.text.textChanged,
            self.size.valueChanged,
            self.angle.valueChanged,
            self.opacity.valueChanged,
            self.tiled.toggled,
        ):
            signal.connect(lambda *_: self._refresh())
        self._paint_color_button()
        self._refresh()
        return widget

    def _pick_color(self):
        chosen = QColorDialog.getColor(QColor(self.color), None, t("watermark.color"))
        if chosen.isValid():
            self.color = chosen.name()
            self._paint_color_button()
            self._refresh()

    def _paint_color_button(self):
        swatch = QPixmap(18, 18)
        swatch.fill(Qt.transparent)
        painter = QPainter(swatch)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(theme.color("border_strong")))
        painter.setBrush(QColor(self.color))
        painter.drawRoundedRect(QRectF(0.5, 0.5, 17, 17), 5, 5)
        painter.end()
        self.color_button.setIcon(swatch)
        self.color_button.setText(f"  {self.color.upper()}")
        self.color_button.setStyleSheet("QPushButton { text-align: left; padding-left: 10px; }")

    def _refresh(self):
        self.preview.set_options(
            text=self.text.text(),
            font_size=self.size.value(),
            angle=self.angle.value(),
            opacity=self.opacity.value() / 100,
            color=self.color,
            tiled=self.tiled.isChecked(),
        )

    def on_files_changed(self, page):
        entries = page.entries()
        if not entries:
            self.preview.set_base(None, 595)
            return
        page.request_preview(entries[0], self.preview.set_base)

    def collect(self, page):
        text = self.text.text().strip()
        if not text:
            raise UserError(t("watermark.empty"))
        return {
            "text": text,
            "size": self.size.value(),
            "angle": self.angle.value(),
            "opacity": self.opacity.value() / 100,
            "color": self.color,
            "tiled": self.tiled.isChecked(),
            "under": self.under.isChecked(),
            "pages": self.pages.text(),
        }

    def execute(self, entries, values, ctx):
        return self.batch(
            entries,
            ctx,
            "_watermarked",
            lambda e, dst, progress: core.watermark(
                e.path,
                dst,
                values["text"],
                font_size=values["size"],
                color=values["color"],
                opacity=values["opacity"],
                angle=values["angle"],
                tiled=values["tiled"],
                under=values["under"],
                pages=values["pages"],
                password=e.password,
                progress=progress,
            ),
        )


class PageNumbersTool(Tool):
    id, icon, category = "numbers", "numbers", "edit"

    def build_options(self, page):
        widget, layout = form()
        self.position = QComboBox()
        for value in ("bottom-center", "bottom-right", "bottom-left", "top-center", "top-right", "top-left"):
            self.position.addItem(t(f"numbers.{value}"), value)
        labeled(layout, t("numbers.position"), self.position)
        self.template = QComboBox()
        self.template.setEditable(True)
        word = "Sayfa" if i18n.language() == "tr" else "Page"
        for preset in ("{n}", "{n} / {total}", f"{word} {{n}}", f"{word} {{n}} / {{total}}", "- {n} -"):
            self.template.addItem(preset)
        self.template.setCurrentIndex(1)
        labeled(layout, t("numbers.format"), self.template, t("numbers.format_hint"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        self.start = spin(0, 99999, 1)
        self.size = spin(6, 48, 11, " pt")
        for col, (label, box) in enumerate(((t("numbers.start"), self.start), (t("numbers.font_size"), self.size))):
            title = QLabel(label)
            title.setStyleSheet("font-weight: 600;")
            grid.addWidget(title, 0, col)
            grid.addWidget(box, 1, col)
        layout.addLayout(grid)
        self.skip = QCheckBox(t("numbers.skip_first"))
        layout.addWidget(self.skip)
        return widget

    def collect(self, page):
        template = self.template.currentText().strip() or "{n}"
        return {
            "position": self.position.currentData(),
            "template": template,
            "start": self.start.value(),
            "size": self.size.value(),
            "skip": self.skip.isChecked(),
        }

    def execute(self, entries, values, ctx):
        return self.batch(
            entries,
            ctx,
            "_numbered",
            lambda e, dst, progress: core.page_numbers(
                e.path,
                dst,
                position=values["position"],
                template=values["template"],
                start=values["start"],
                font_size=values["size"],
                skip_first=values["skip"],
                password=e.password,
                progress=progress,
            ),
        )


# --------------------------------------------------------------------------- security / metadata


class ProtectTool(Tool):
    id, icon, category = "protect", "protect", "security"

    def build_options(self, page):
        widget, layout = form()
        self.password = labeled(layout, t("protect.password"), password_edit())
        self.confirm = labeled(layout, t("protect.confirm"), password_edit())
        self.allow_print = QCheckBox(t("protect.allow_print"))
        self.allow_print.setChecked(True)
        self.allow_copy = QCheckBox(t("protect.allow_copy"))
        self.allow_copy.setChecked(True)
        self.allow_modify = QCheckBox(t("protect.allow_modify"))
        for box in (self.allow_print, self.allow_copy, self.allow_modify):
            layout.addWidget(box)
        note(layout, t("protect.note"))
        return widget

    def collect(self, page):
        if not self.password.text():
            raise UserError(t("protect.empty"))
        if self.password.text() != self.confirm.text():
            raise UserError(t("protect.mismatch"))
        return {
            "password": self.password.text(),
            "print": self.allow_print.isChecked(),
            "copy": self.allow_copy.isChecked(),
            "modify": self.allow_modify.isChecked(),
        }

    def execute(self, entries, values, ctx):
        return self.batch(
            entries,
            ctx,
            "_protected",
            lambda e, dst, progress: core.protect(
                e.path,
                dst,
                values["password"],
                allow_print=values["print"],
                allow_copy=values["copy"],
                allow_modify=values["modify"],
                password=e.password,
                progress=progress,
            ),
        )


class UnlockTool(Tool):
    id, icon, category = "unlock", "unlock", "security"
    prompt_passwords = False

    def build_options(self, page):
        widget, layout = form()
        self.password = labeled(layout, t("unlock.password"), password_edit())
        note(layout, t("unlock.note"))
        return widget

    def collect(self, page):
        if not self.password.text():
            raise UserError(t("unlock.empty"))
        return {"password": self.password.text()}

    def execute(self, entries, values, ctx):
        return self.batch(
            entries,
            ctx,
            "_unlocked",
            lambda e, dst, progress: core.unlock(e.path, dst, values["password"], progress=progress),
        )


class MetadataTool(Tool):
    id, icon, category = "metadata", "metadata", "edit"
    FIELDS = ("title", "author", "subject", "keywords", "creator", "producer")

    def build_options(self, page):
        widget, layout = form()
        self.strip = QCheckBox(t("metadata.strip"))
        layout.addWidget(self.strip)
        self.edits: dict[str, QLineEdit] = {}
        for name in self.FIELDS:
            self.edits[name] = labeled(layout, t(f"metadata.{name}"), QLineEdit())
        self.strip.toggled.connect(lambda on: [edit.setEnabled(not on) for edit in self.edits.values()])
        return widget

    def on_files_changed(self, page):
        entries = page.entries()
        if not entries:
            return
        try:
            values = core.read_metadata(entries[0].path, entries[0].password)
        except core.OfflinePDFError:
            return
        for name, edit in self.edits.items():
            edit.setText(values.get(name, ""))

    def collect(self, page):
        return {"strip": self.strip.isChecked(), "values": {k: e.text() for k, e in self.edits.items()}}

    def execute(self, entries, values, ctx):
        if values["strip"]:
            return self.batch(
                entries,
                ctx,
                "_clean",
                lambda e, dst, progress: core.strip_metadata(e.path, dst, password=e.password, progress=progress),
            )
        return self.batch(
            entries,
            ctx,
            "_edited",
            lambda e, dst, progress: core.set_metadata(e.path, dst, values["values"], password=e.password, progress=progress),
        )


class InfoTool(Tool):
    id, icon, category = "info", "info", "optimize"
    multi = False
    runnable = False

    def build_options(self, page):
        widget, layout = form()
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(8)
        layout.addLayout(self.grid)
        self.copy = QPushButton(t("info.copy"))
        self.copy.setVisible(False)
        self.copy.clicked.connect(self._copy)
        layout.addWidget(self.copy, 0, Qt.AlignLeft)
        self.status = note(layout, t("common.add_files_first"))
        self._rows: list[tuple[str, str]] = []
        return widget

    def on_files_changed(self, page):
        entries = page.entries()
        self._clear()
        if not entries:
            self.status.setText(t("common.add_files_first"))
            self.copy.setVisible(False)
            return
        self.status.setText(t("common.loading"))
        entry = entries[0]
        page.run_background(lambda progress: core.get_info(entry.path, entry.password), self._show, page.show_error)

    def _clear(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows = []

    def _show(self, info):
        yes, no, dash = t("common.yes"), t("common.no"), t("info.empty_value")
        rows = [
            (t("info.pages"), str(info.pages)),
            (t("info.file_size"), human_size(info.file_size)),
            (t("info.page_sizes"), "\n".join(f"{label}  ×{count}" for label, count in info.page_sizes)),
            (t("info.version"), info.version),
            (t("info.encrypted"), yes if info.encrypted else no),
            (t("info.text"), yes if info.has_text else t("info.text_no")),
            (t("info.images"), str(info.images)),
            (t("info.bookmarks"), str(info.bookmarks)),
            (t("info.attachments"), str(info.attachments)),
            (t("info.forms"), yes if info.has_forms else no),
            (t("info.linearized"), yes if info.linearized else no),
            (t("info.created"), info.created or dash),
            (t("info.modified"), info.modified or dash),
        ]
        for name in MetadataTool.FIELDS:
            rows.append((t(f"metadata.{name}"), info.metadata.get(name) or dash))
        self._clear()
        for row, (key, value) in enumerate(rows):
            key_label = QLabel(key)
            key_label.setObjectName("InfoKey")
            value_label = QLabel(value)
            value_label.setObjectName("InfoValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.grid.addWidget(key_label, row, 0, Qt.AlignTop)
            self.grid.addWidget(value_label, row, 1)
        self.grid.setColumnStretch(1, 1)
        self._rows = rows
        self.status.setText("")
        self.copy.setVisible(True)

    def _copy(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText("\n".join(f"{k}: {v}" for k, v in self._rows))
        self.status.setText(t("info.copied"))


ALL_TOOLS: list[type[Tool]] = [
    MergeTool,
    SplitTool,
    ExtractTool,
    DeleteTool,
    ReorderTool,
    RotateTool,
    CompressTool,
    ImagesToPdfTool,
    PdfToImagesTool,
    WatermarkTool,
    PageNumbersTool,
    ProtectTool,
    UnlockTool,
    MetadataTool,
    InfoTool,
]

CATEGORIES = ["organize", "optimize", "convert", "edit", "security"]


def tool_by_id(tool_id: str) -> type[Tool]:
    for cls in ALL_TOOLS:
        if cls.id == tool_id:
            return cls
    raise KeyError(tool_id)
