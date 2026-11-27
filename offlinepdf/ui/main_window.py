"""Main window: header bar + stacked home / tool pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, i18n
from ..i18n import t
from . import icons, theme
from .about import AboutDialog
from .home import HomePage
from .resources import resource_path
from .tool_page import ToolPage
from .tools import tool_by_id


class MainWindow(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle(APP_NAME)
        icon_path = resource_path("assets/icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1200, 800)
        self.setMinimumSize(980, 660)
        self.current_tool: str | None = None
        self.pages: dict[str, ToolPage] = {}
        self.build()

    # ------------------------------------------------------------------ build

    def build(self) -> None:
        QApplication.instance().setStyleSheet(theme.stylesheet())
        root = QWidget()
        root.setObjectName("Root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header())
        self.stack = QStackedWidget()
        self.home = HomePage()
        self.home.tool_selected.connect(self.open_tool)
        self.stack.addWidget(self.home)
        layout.addWidget(self.stack, 1)
        old = self.centralWidget()
        self.setCentralWidget(root)
        if old is not None:
            old.deleteLater()
        self.pages = {}

    def _header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(62)
        row = QHBoxLayout(header)
        row.setContentsMargins(22, 8, 16, 8)
        row.setSpacing(10)
        logo = QLabel()
        pixmap = QPixmap(str(resource_path("assets/icon.png")))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setCursor(Qt.PointingHandCursor)
        logo.mouseReleaseEvent = lambda event: self.show_home()
        row.addWidget(logo)
        name = QLabel(APP_NAME)
        name.setObjectName("AppName")
        name.setCursor(Qt.PointingHandCursor)
        name.mouseReleaseEvent = lambda event: self.show_home()
        row.addWidget(name)
        chip = QLabel(t("app.offline_chip"))
        chip.setObjectName("Chip")
        chip.setFixedHeight(24)
        chip.setAlignment(Qt.AlignCenter)
        chip.setToolTip(t("app.privacy"))
        row.addSpacing(6)
        row.addWidget(chip, 0, Qt.AlignVCenter)
        row.addStretch(1)

        self.language = QComboBox()
        for code, label in i18n.LANGUAGES.items():
            self.language.addItem(label, code)
        self.language.setCurrentIndex(max(0, self.language.findData(i18n.language())))
        self.language.setToolTip(t("app.language"))
        self.language.currentIndexChanged.connect(lambda *_: self.set_language(self.language.currentData()))
        row.addWidget(self.language)

        dark = theme.mode() == "dark"
        self.theme_button = QToolButton()
        self.theme_button.setObjectName("IconButton")
        self.theme_button.setIcon(icons.icon("sun" if dark else "moon", theme.color("text"), 20))
        self.theme_button.setToolTip(t("app.theme_light") if dark else t("app.theme_dark"))
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)
        row.addWidget(self.theme_button)

        about = QToolButton()
        about.setObjectName("IconButton")
        about.setIcon(icons.icon("about", theme.color("text"), 20))
        about.setToolTip(t("app.about"))
        about.setCursor(Qt.PointingHandCursor)
        about.clicked.connect(lambda: AboutDialog(self).exec())
        row.addWidget(about)
        return header

    # ------------------------------------------------------------------ navigation

    def open_tool(self, tool_id: str) -> ToolPage:
        page = self.pages.get(tool_id)
        if page is None:
            page = ToolPage(tool_by_id(tool_id)(), self.settings)
            page.back_requested.connect(self.show_home)
            self.stack.addWidget(page)
            self.pages[tool_id] = page
        self.stack.setCurrentWidget(page)
        self.current_tool = tool_id
        return page

    def show_home(self) -> None:
        self.stack.setCurrentWidget(self.home)
        self.current_tool = None

    # ------------------------------------------------------------------ preferences

    def _rebuild_keep_place(self) -> None:
        current = self.current_tool
        self.build()
        if current:
            self.open_tool(current)

    def set_language(self, code: str) -> None:
        if code == i18n.language():
            return
        i18n.set_language(code)
        self.settings.setValue("language", code)
        self._rebuild_keep_place()

    def toggle_theme(self) -> None:
        theme.set_mode("light" if theme.mode() == "dark" else "dark")
        self.settings.setValue("theme", theme.mode())
        self._rebuild_keep_place()
