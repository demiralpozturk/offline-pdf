"""About dialog with author links (taken from app_info.py)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import APP_NAME, __version__, app_info
from ..i18n import t
from . import icons, theme
from .resources import resource_path


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("about.title"))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(14)
        logo = QLabel()
        pixmap = QPixmap(str(resource_path("assets/icon.png")))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        top.addWidget(logo)
        names = QVBoxLayout()
        name = QLabel(APP_NAME)
        name.setStyleSheet("font-size: 18pt; font-weight: 800;")
        version = QLabel(t("app.version", version=__version__))
        version.setObjectName("Muted")
        names.addWidget(name)
        names.addWidget(version)
        top.addLayout(names, 1)
        layout.addLayout(top)

        body = QLabel(t("about.body"))
        body.setWordWrap(True)
        layout.addWidget(body)

        author = QLabel(t("app.made_by", author=f"<b>{app_info.AUTHOR}</b>"))
        author.setTextFormat(Qt.RichText)
        layout.addWidget(author)

        links = QHBoxLayout()
        links.setSpacing(8)
        for label, url, icon_name in (
            (t("about.github"), app_info.GITHUB_URL, "link"),
            (t("about.repo"), app_info.REPO_URL, "heart"),
            (t("about.linkedin"), app_info.LINKEDIN_URL, "link"),
            (t("about.email"), f"mailto:{app_info.CONTACT_EMAIL}" if app_info.CONTACT_EMAIL else "", "file"),
        ):
            if not url:
                continue
            button = QPushButton(f" {label}")
            button.setIcon(icons.icon(icon_name, theme.color("accent"), 14))
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(url.replace("mailto:", ""))
            button.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            links.addWidget(button)
        links.addStretch(1)
        layout.addLayout(links)

        legal = QLabel(f"{t('about.license')}\n{t('about.third_party')}")
        legal.setObjectName("Muted")
        legal.setWordWrap(True)
        layout.addWidget(legal)

        close = QPushButton(t("about.close"))
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
