"""Start screen: hero, search and a grid of tool cards grouped by category."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, app_info
from ..i18n import t
from . import icons, theme
from .tools import ALL_TOOLS, CATEGORIES
from .widgets import IconBadge, glyph_label


class ToolCard(QFrame):
    clicked = Signal(str)

    def __init__(self, tool_cls, parent=None):
        super().__init__(parent)
        self.tool_id = tool_cls.id
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(148)
        self.title_text = t(f"tool.{tool_cls.id}.title")
        self.desc_text = t(f"tool.{tool_cls.id}.desc")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(8)
        layout.addWidget(IconBadge(tool_cls.icon, theme.CATEGORY_COLORS[tool_cls.category], 44))
        title = QLabel(self.title_text)
        title.setObjectName("CardTitle")
        desc = QLabel(self.desc_text)
        desc.setObjectName("CardDesc")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(title)
        layout.addWidget(desc, 1)
        for label in (title, desc):
            label.setAttribute(Qt.WA_TransparentForMouseEvents)

    def matches(self, query: str) -> bool:
        query = query.casefold().strip()
        return not query or query in self.title_text.casefold() or query in self.desc_text.casefold()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.tool_id)
        super().mouseReleaseEvent(event)


class HomePage(QWidget):
    tool_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        self.layout_ = QVBoxLayout(content)
        self.layout_.setContentsMargins(48, 34, 48, 28)
        self.layout_.setSpacing(10)

        hero = QLabel(t("app.tagline"))
        hero.setObjectName("HeroTitle")
        self.layout_.addWidget(hero)
        sub_row = QHBoxLayout()
        sub_row.setSpacing(8)
        sub_row.addWidget(glyph_label("shield", 15, theme.color("chip_text")), 0, Qt.AlignVCenter)
        sub = QLabel(t("app.privacy"))
        sub.setObjectName("HeroSub")
        sub.setWordWrap(True)
        sub_row.addWidget(sub, 1)
        self.layout_.addLayout(sub_row)
        self.layout_.addSpacing(10)

        self.search = QLineEdit()
        self.search.setPlaceholderText(t("app.search"))
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(420)
        self.search.setMinimumHeight(38)
        self.search.addAction(icons.icon("search", theme.color("muted"), 16), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self.apply_filter)
        self.layout_.addWidget(self.search)
        self.layout_.addSpacing(12)

        self.sections: list[tuple[QLabel, QWidget, QGridLayout, list[ToolCard]]] = []
        for category in CATEGORIES:
            tools = [cls for cls in ALL_TOOLS if cls.category == category]
            title = QLabel(t(f"cat.{category}").upper())
            title.setObjectName("SectionTitle")
            holder = QWidget()
            grid = QGridLayout(holder)
            grid.setContentsMargins(0, 4, 0, 14)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)
            cards = []
            for cls in tools:
                card = ToolCard(cls)
                card.clicked.connect(self.tool_selected.emit)
                cards.append(card)
            self.layout_.addWidget(title)
            self.layout_.addWidget(holder)
            self.sections.append((title, holder, grid, cards))

        self.no_results = QLabel()
        self.no_results.setObjectName("Muted")
        self.no_results.hide()
        self.layout_.addWidget(self.no_results)
        self.layout_.addStretch(1)

        footer = QLabel(self._footer_html())
        footer.setObjectName("Footer")
        footer.setOpenExternalLinks(True)
        footer.setTextFormat(Qt.RichText)
        self.layout_.addWidget(footer)
        self._columns = 0
        self._relayout(4)

    def _footer_html(self) -> str:
        accent = theme.color("accent")
        links = [f'<a style="color:{accent}; text-decoration:none" href="{app_info.REPO_URL}">{t("app.source")}</a>']
        if app_info.GITHUB_URL:
            links.append(f'<a style="color:{accent}; text-decoration:none" href="{app_info.GITHUB_URL}">GitHub</a>')
        if app_info.LINKEDIN_URL:
            links.append(f'<a style="color:{accent}; text-decoration:none" href="{app_info.LINKEDIN_URL}">LinkedIn</a>')
        if app_info.CONTACT_EMAIL:
            links.append(f'<a style="color:{accent}; text-decoration:none" href="mailto:{app_info.CONTACT_EMAIL}">{app_info.CONTACT_EMAIL}</a>')
        made_by = t("app.made_by", author=f"<b>{app_info.AUTHOR}</b>")
        return f"{made_by} &nbsp;·&nbsp; " + " &nbsp;·&nbsp; ".join(links) + f" &nbsp;·&nbsp; v{__version__} &nbsp;·&nbsp; MIT"

    def _relayout(self, columns: int) -> None:
        if columns == self._columns:
            return
        self._columns = columns
        for _, _, grid, cards in self.sections:
            for card in cards:
                grid.removeWidget(card)
            visible = [card for card in cards if card.matches(self.search.text())]
            for i, card in enumerate(visible):
                grid.addWidget(card, i // columns, i % columns)
            for col in range(columns):
                grid.setColumnStretch(col, 1)
            for col in range(columns, 8):
                grid.setColumnStretch(col, 0)

    def resizeEvent(self, event) -> None:
        width = event.size().width() - 96
        self._relayout(max(2, min(5, width // 250)))
        super().resizeEvent(event)

    def apply_filter(self, text: str) -> None:
        any_visible = False
        for title, holder, grid, cards in self.sections:
            matched = [card for card in cards if card.matches(text)]
            for card in cards:
                card.setVisible(card in matched)
            title.setVisible(bool(matched))
            holder.setVisible(bool(matched))
            any_visible = any_visible or bool(matched)
        columns, self._columns = self._columns, 0
        self._relayout(columns)
        self.no_results.setText(t("app.no_results", query=text))
        self.no_results.setVisible(not any_visible)
