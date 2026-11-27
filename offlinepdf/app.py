"""Application entry point."""

from __future__ import annotations

import os
import sys


def _prepare_environment() -> None:
    # Headless runs (tests, screenshots, self-test) need a font directory on Windows.
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen" and os.name == "nt":
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))


def create_app(argv: list[str] | None = None):
    """Create the QApplication with saved language/theme applied."""
    _prepare_environment()
    from PySide6.QtCore import QLocale, QSettings, Qt
    from PySide6.QtGui import QFont, QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME, i18n
    from .ui import theme
    from .ui.resources import resource_path

    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setFont(QFont("Segoe UI", 10))
    icon_path = resource_path("assets/icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    settings = QSettings(APP_NAME, APP_NAME)
    language = settings.value("language", "") or ("tr" if QLocale.system().name().lower().startswith("tr") else "en")
    i18n.set_language(str(language))
    saved_theme = settings.value("theme", "")
    if not saved_theme:
        try:
            saved_theme = "dark" if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else "light"
        except AttributeError:
            saved_theme = "light"
    theme.set_mode(str(saved_theme))
    return app, settings


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" in argv:
        from .selftest import run_selftest

        position = argv.index("--selftest")
        target = argv[position + 1] if len(argv) > position + 1 else None
        return run_selftest(target)

    app, settings = create_app(argv)
    from .ui.main_window import MainWindow

    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
