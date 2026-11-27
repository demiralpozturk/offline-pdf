"""Smoke tests for the Qt interface, run headless (QT_QPA_PLATFORM=offscreen)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from offlinepdf import i18n, samples  # noqa: E402
from offlinepdf.app import create_app  # noqa: E402
from offlinepdf.ui import theme, worker  # noqa: E402
from offlinepdf.ui.main_window import MainWindow  # noqa: E402
from offlinepdf.ui.tools import ALL_TOOLS  # noqa: E402


def settle():
    for _ in range(5):
        worker.wait_all(30000)
        QApplication.processEvents()


@pytest.fixture(scope="module")
def app():
    application, _ = create_app(["test"])
    return application


@pytest.fixture
def window(app, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    i18n.set_language("en")
    theme.set_mode("light")
    win = MainWindow(settings)
    win.resize(1200, 800)
    win.show()
    yield win
    win.close()


@pytest.fixture(scope="module")
def docs(tmp_path_factory):
    return samples.make_all(tmp_path_factory.mktemp("docs"))


def test_every_tool_page_opens(window):
    for cls in ALL_TOOLS:
        page = window.open_tool(cls.id)
        assert page.tool.id == cls.id
    window.show_home()


def test_merge_through_the_ui(window, docs, tmp_path):
    page = window.open_tool("merge")
    page.output.set_folder(str(tmp_path))
    page.add_files([str(docs["invoice"]), str(docs["report"])])
    assert len(page.entries()) == 2
    page.start()
    settle()
    assert page.status.isVisible()
    merged = tmp_path / "merged.pdf"
    assert merged.exists()
    from offlinepdf.core import page_count

    assert page_count(merged) == 9


def test_extract_selection_syncs_with_text(window, docs, tmp_path):
    page = window.open_tool("extract")
    page.output.set_folder(str(tmp_path))
    page.add_files([str(docs["report"])])
    settle()
    page.grid.set_selected_indices([0, 1, 2, 6])
    assert page.tool.pages.text() == "1-3, 7"
    page.start()
    settle()
    outputs = list(tmp_path.glob("*_extract.pdf"))
    assert len(outputs) == 1


def test_wrong_file_type_is_rejected(window, tmp_path):
    page = window.open_tool("compress")
    other = tmp_path / "notes.txt"
    other.write_text("hello")
    page.add_files([str(other)])
    assert page.entries() == []
    assert page.status.isVisible()


def test_validation_message(window, docs):
    page = window.open_tool("protect")
    page.add_files([str(docs["invoice"])])
    page.tool.password.setText("a")
    page.tool.confirm.setText("b")
    page.start()
    assert page.status.title.text() == i18n.t("protect.mismatch")


def test_language_and_theme_switch_keep_tool(window):
    window.open_tool("split")
    window.set_language("tr")
    assert window.current_tool == "split"
    assert window.pages["split"].tool.title() == "PDF böl"
    window.toggle_theme()
    assert theme.mode() == "dark"
    window.set_language("en")
    window.toggle_theme()
