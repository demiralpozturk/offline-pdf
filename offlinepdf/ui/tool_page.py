"""One screen per tool: files on the left, options and Start on the right."""

from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from .. import core
from ..core.document import is_image, is_pdf
from ..i18n import t
from . import icons, theme, worker
from .tools import Context, Result, Tool, UserError
from .widgets import (
    DropZone,
    FileEntry,
    FileList,
    IconBadge,
    OutputRow,
    PageGrid,
    glyph_label,
    open_path,
    reveal_in_folder,
)


def error_message(exc: Exception) -> str:
    if isinstance(exc, core.OfflinePDFError):
        params = dict(exc.params)
        detail = exc.detail or ""
        params.setdefault("name", Path(detail.split(": ")[0]).name if detail else "")
        params.setdefault("detail", detail)
        if exc.code == "error.invalid_range" and params.get("page_count"):
            return t("error.invalid_range_max", **params)
        return t(exc.code, **params)
    return t("error.generic", detail=str(exc) or exc.__class__.__name__)


class StatusCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        top = QHBoxLayout()
        self.icon = QLabel()
        self.title = QLabel()
        self.title.setStyleSheet("font-weight: 700; font-size: 11pt; background: transparent;")
        top.addWidget(self.icon)
        top.addWidget(self.title, 1)
        layout.addLayout(top)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("background: transparent;")
        self.message.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.message)
        buttons = QHBoxLayout()
        self.open_folder = QPushButton(t("common.open_folder"))
        self.open_file = QPushButton(t("common.open_file"))
        buttons.addWidget(self.open_folder)
        buttons.addWidget(self.open_file)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.open_folder.clicked.connect(lambda: self._target and reveal_in_folder(self._target))
        self.open_file.clicked.connect(lambda: self._target and open_path(self._target))
        self._target: Path | None = None
        self.hide()

    def show_success(self, result: Result) -> None:
        self.setObjectName("ResultCard")
        self._restyle()
        self.icon.setText(icons.glyph("check"))
        self.icon.setStyleSheet(f"color: {theme.color('success')}; background: transparent;" + icons.glyph_css(18))
        self.title.setText(t("common.done"))
        lines = []
        if len(result.outputs) == 1:
            lines.append(t("common.saved_one", name=result.outputs[0].name))
        elif result.outputs:
            lines.append(t("common.saved_files", n=len(result.outputs)))
        if result.message:
            lines.append(result.message)
        self.message.setText("\n".join(lines))
        self._target = result.outputs[0] if result.outputs else None
        self.open_folder.setVisible(bool(result.outputs))
        self.open_file.setVisible(len(result.outputs) == 1)
        self.show()

    def show_error(self, message: str) -> None:
        self.setObjectName("ErrorCard")
        self._restyle()
        self.icon.setText(icons.glyph("error"))
        self.icon.setStyleSheet(f"color: {theme.color('danger')}; background: transparent;" + icons.glyph_css(18))
        self.title.setText(message)
        self.title.setWordWrap(True)
        self.message.setText("")
        self.message.setVisible(False)
        self.open_folder.hide()
        self.open_file.hide()
        self.show()

    def _restyle(self) -> None:
        self.message.setVisible(True)
        self.style().unpolish(self)
        self.style().polish(self)


class ToolPage(QWidget):
    back_requested = Signal()

    def __init__(self, tool: Tool, settings, parent=None):
        super().__init__(parent)
        self.tool = tool
        self.settings = settings
        self.grid: PageGrid | None = None
        self.file_list: FileList | None = None
        self._entries: dict[str, FileEntry] = {}
        self._jobs = []
        self._thumb_signals = worker.ThumbSignals()
        self._thumb_signals.ready.connect(self._on_list_thumb)
        self.setAcceptDrops(True)
        self._build()

    # ------------------------------------------------------------------ layout

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 14, 28, 22)
        root.setSpacing(14)

        back = QPushButton(f"  {t('common.back')}")
        back.setObjectName("Ghost")
        back.setIcon(icons.icon("back", theme.color("muted"), 16))
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self.back_requested.emit)
        top = QHBoxLayout()
        top.addWidget(back)
        top.addStretch(1)
        root.addLayout(top)

        title_row = QHBoxLayout()
        title_row.setSpacing(14)
        title_row.addWidget(IconBadge(self.tool.icon, theme.CATEGORY_COLORS[self.tool.category], 52))
        texts = QVBoxLayout()
        texts.setSpacing(2)
        title = QLabel(self.tool.title())
        title.setObjectName("PageTitle")
        desc = QLabel(self.tool.desc())
        desc.setObjectName("PageDesc")
        texts.addWidget(title)
        texts.addWidget(desc)
        title_row.addLayout(texts, 1)
        root.addLayout(title_row)

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        # Left: files
        left = QFrame()
        left.setObjectName("Panel")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        self.left_stack = QStackedLayout()
        left_layout.addLayout(self.left_stack)
        self.drop = DropZone(self.tool.inputs, self.tool.multi or self.tool.page_mode is None)
        self.drop.files_dropped.connect(self.add_files)
        self.left_stack.addWidget(self.drop)
        self.left_stack.addWidget(self._build_files_view())
        body.addWidget(left, 3)

        # Right: options + start
        right_frame = QFrame()
        right_frame.setObjectName("Panel")
        right_frame.setFixedWidth(370)
        right_outer = QVBoxLayout(right_frame)
        right_outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        right = QVBoxLayout(inner)
        right.setContentsMargins(18, 16, 18, 16)
        right.setSpacing(14)
        heading = QLabel(t("info.properties") if not self.tool.runnable else t("common.options"))
        heading.setObjectName("PanelTitle")
        right.addWidget(heading)
        options = self.tool.build_options(self)
        if options is not None:
            right.addWidget(options)
        right.addStretch(1)
        scroll.setWidget(inner)
        right_outer.addWidget(scroll, 1)

        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(18, 10, 18, 16)
        footer_layout.setSpacing(10)
        self.output = OutputRow(self.settings)
        self.start_button = QPushButton(t("common.start"))
        self.start_button.setObjectName("Primary")
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.clicked.connect(self.start)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setFixedHeight(10)
        self.progress.hide()
        self.status = StatusCard()
        if self.tool.runnable:
            footer_layout.addWidget(self.output)
            footer_layout.addWidget(self.start_button)
            footer_layout.addWidget(self.progress)
        footer_layout.addWidget(self.status)
        right_outer.addWidget(footer)
        body.addWidget(right_frame)

    def _build_files_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        bar = QHBoxLayout()
        self.files_label = QLabel()
        self.files_label.setStyleSheet("font-weight: 700;")
        bar.addWidget(self.files_label, 1)
        self.toolbar_buttons: list[QPushButton] = []

        def button(text: str, icon_name: str, handler) -> QPushButton:
            b = QPushButton(f" {text}")
            b.setIcon(icons.icon(icon_name, theme.color("text"), 14))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(handler)
            bar.addWidget(b)
            self.toolbar_buttons.append(b)
            return b

        if self.tool.page_mode in ("select", "delete"):
            button(t("common.select_all"), "check", lambda: self.grid.set_selected_indices(list(range(self.grid.count()))))
            button(t("common.select_none"), "close", lambda: self.grid.set_selected_indices([]))
        if self.tool.reorderable:
            button(t("common.move_up"), "up", lambda: self.file_list.move_selected(-1))
            button(t("common.move_down"), "down", lambda: self.file_list.move_selected(1))
        if self.tool.page_mode is None:
            button(t("common.add_more"), "add", self.drop.browse)
            button(t("common.remove"), "delete", self.remove_selected)
        button(t("common.clear"), "close", self.clear)
        layout.addLayout(bar)

        if self.tool.page_mode:
            self.grid = PageGrid("delete" if self.tool.page_mode == "delete" else self.tool.page_mode)
            self.grid.selection_changed_pages.connect(lambda indices: self.tool.on_pages_selected(self, indices))
            layout.addWidget(self.grid, 1)
        else:
            self.file_list = FileList(self.tool.reorderable, self.tool.numbered)
            self.file_list.order_changed.connect(lambda: self.tool.on_files_changed(self))
            layout.addWidget(self.file_list, 1)
        return view

    # ------------------------------------------------------------------ files

    def entries(self) -> list[FileEntry]:
        if self.file_list is not None:
            return [self._entries[p] for p in self.file_list.paths() if p in self._entries]
        return list(self._entries.values())

    def _ask_password(self, entry: FileEntry) -> bool:
        for _ in range(3):
            password, ok = QInputDialog.getText(
                self, t("common.password_title"), t("common.password_prompt", name=entry.name), QLineEdit.Password
            )
            if not ok:
                return False
            try:
                entry.pages = core.page_count(entry.path, password)
            except core.WrongPasswordError:
                continue
            entry.password = password
            return True
        return False

    def add_files(self, paths: list[str]) -> None:
        wanted = is_image if self.tool.inputs == "image" else is_pdf
        accepted = [Path(p) for p in paths if wanted(p) and Path(p).is_file()]
        rejected = [Path(p).name for p in paths if not (wanted(p) and Path(p).is_file())]
        if not self.tool.multi:
            accepted = accepted[:1]
            if accepted:
                self.clear()
        added: list[FileEntry] = []
        for path in accepted:
            key = str(path)
            if key in self._entries:
                continue
            entry = FileEntry(path=path, size=path.stat().st_size)
            if self.tool.inputs == "pdf":
                try:
                    entry.pages = core.page_count(path)
                except core.PasswordRequiredError:
                    entry.locked = True
                    if self.tool.prompt_passwords and not self._ask_password(entry):
                        continue
                except core.OfflinePDFError:
                    rejected.append(path.name)
                    continue
            self._entries[key] = entry
            added.append(entry)
        if rejected:
            self.show_error(t("error.unsupported", names=", ".join(rejected[:5])))
        else:
            self.status.hide()
        if not added:
            self._refresh()
            return
        if self.grid is not None:
            entry = added[0]
            self.grid.load(str(entry.path), entry.pages or 0, entry.password)
        else:
            for entry in added:
                self.file_list.add_entry(entry)
            self._load_list_thumbnails(added)
        self._refresh()
        self.tool.on_files_changed(self)

    def _load_list_thumbnails(self, entries: list[FileEntry]) -> None:
        for entry in entries:
            if self.tool.inputs == "image":
                reader = QImageReader(str(entry.path))
                reader.setAutoTransform(True)
                size = reader.size()
                if size.isValid():
                    reader.setScaledSize(size.scaled(QSize(120, 160), Qt.KeepAspectRatio))
                image = reader.read()
                if not image.isNull():
                    self.file_list.set_thumbnail(str(entry.path), image)
                continue
            if entry.locked and not entry.password:
                continue
            job = worker.ThumbnailJob(str(entry.path), str(entry.path), [0], 120, entry.password, self._thumb_signals)
            self._jobs.append(job)
            worker.THUMB_POOL.start(job)

    def _on_list_thumb(self, token: str, index: int, image: QImage) -> None:
        if self.file_list is not None:
            self.file_list.set_thumbnail(token, image)

    def remove_selected(self) -> None:
        if self.file_list is None:
            return
        for item in self.file_list.selectedItems():
            self._entries.pop(item.data(Qt.UserRole), None)
            self.file_list.takeItem(self.file_list.row(item))
        self._refresh()
        self.tool.on_files_changed(self)

    def clear(self) -> None:
        self._entries.clear()
        if self.file_list is not None:
            self.file_list.clear()
        if self.grid is not None:
            self.grid.clear()
        self.status.hide()
        self._refresh()
        self.tool.on_files_changed(self)

    def _refresh(self) -> None:
        entries = self.entries()
        self.left_stack.setCurrentIndex(1 if entries else 0)
        if self.grid is not None and entries:
            entry = entries[0]
            self.files_label.setText(f"{entry.name}  ·  {entry.meta_text()}")
        elif entries:
            total_pages = sum(e.pages or 0 for e in entries)
            label = t("common.file_count_one") if len(entries) == 1 else t("common.files_count", n=len(entries))
            if self.tool.inputs == "pdf" and total_pages:
                label += f"  ·  {t('common.pages_count', n=total_pages)}"
            self.files_label.setText(label)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            self.add_files(files)
            event.acceptProposedAction()

    # ------------------------------------------------------------------ running

    def run_background(self, fn, on_done, on_error=None) -> None:
        signals = worker.start(fn)
        signals.finished.connect(on_done)
        if on_error is not None:
            signals.failed.connect(lambda exc: on_error(error_message(exc)))
        self._jobs.append(signals)

    def request_preview(self, entry: FileEntry, callback) -> None:
        """Render the first page larger for live previews (watermark)."""

        def job(progress):
            from ..core.render import PDFIUM_LOCK, open_document, render_page

            with open_document(entry.path, entry.password) as doc:
                with PDFIUM_LOCK:
                    first = doc[0]
                    width, _ = first.get_size()
                    first.close()
                image = render_page(doc, 0, dpi=72, max_px=520)
            return worker.pil_to_qimage(image), width

        self.run_background(job, lambda result: callback(QPixmap.fromImage(result[0]), result[1]))

    def show_error(self, message: str) -> None:
        self.status.show_error(message)

    def start(self) -> None:
        entries = self.entries()
        if not entries:
            self.show_error(t("common.add_files_first"))
            return
        if len(entries) < self.tool.min_files:
            self.show_error(t("common.add_at_least", n=self.tool.min_files))
            return
        try:
            values = self.tool.collect(self)
        except UserError as exc:
            self.show_error(str(exc))
            return
        folder = self.output.folder()

        def out_dir_for(source):
            return Path(folder) if folder else Path(source).parent

        self.status.hide()
        self.progress.setValue(0)
        self.progress.show()
        self.start_button.setEnabled(False)
        self.start_button.setText(t("common.working"))
        signals = worker.start(lambda progress: self.tool.execute(entries, values, Context(out_dir_for, progress)))
        signals.progress.connect(self._on_progress)
        signals.finished.connect(self._on_finished)
        signals.failed.connect(self._on_failed)
        self._jobs.append(signals)

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setValue(int(done / max(total, 1) * 1000))

    def _finish_ui(self) -> None:
        self.progress.hide()
        self.start_button.setEnabled(True)
        self.start_button.setText(t("common.start"))

    def _on_finished(self, result: Result) -> None:
        self._finish_ui()
        self.status.show_success(result)

    def _on_failed(self, exc: Exception) -> None:
        self._finish_ui()
        self.show_error(error_message(exc))
