"""Render README screenshots and the demo GIF without opening any window.

Run: python scripts/screenshots.py [output_dir]
Defaults to docs/ (docs/screenshots/*.png and docs/demo.gif).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from offlinepdf import i18n, samples  # noqa: E402
from offlinepdf.app import create_app  # noqa: E402
from offlinepdf.ui import theme, worker  # noqa: E402
from offlinepdf.ui.main_window import MainWindow  # noqa: E402

SIZE = (1280, 820)


def settle(rounds: int = 6) -> None:
    for _ in range(rounds):
        worker.wait_all(20000)
        QApplication.processEvents()


def grab(window: MainWindow, path: Path) -> Image.Image:
    settle()
    window.repaint()
    QApplication.processEvents()
    pixmap = window.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path))
    return Image.open(path).convert("RGB")


def new_window(settings: QSettings, language: str, mode: str) -> MainWindow:
    i18n.set_language(language)
    theme.set_mode(mode)
    window = MainWindow(settings)
    window.resize(*SIZE)
    window.show()
    settle()
    return window


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs"
    shots = out / "screenshots"
    work = Path(tempfile.mkdtemp(prefix="offlinepdf-shots-"))
    docs = samples.make_all(work / "Documents")
    photos = samples.photo_files(work / "Photos", 4)
    results = work / "Output"
    results.mkdir()

    app, _ = create_app([sys.argv[0]])
    settings = QSettings(str(work / "settings.ini"), QSettings.IniFormat)

    frames: list[tuple[Image.Image, int]] = []

    # ---- English, light: home + merge flow (also the GIF)
    window = new_window(settings, "en", "light")
    home = grab(window, shots / "home-light.png")
    frames.append((home, 1600))
    page = window.open_tool("merge")
    frames.append((grab(window, shots / "_merge-empty.png"), 900))
    page.add_files([str(docs["report"]), str(docs["invoice"])])
    frames.append((grab(window, shots / "_merge-2.png"), 700))
    page.add_files([str(docs["brochure"])])
    frames.append((grab(window, shots / "_merge-3.png"), 1100))
    page.file_list.setCurrentRow(2)
    page.file_list.move_selected(-2)
    frames.append((grab(window, shots / "_merge-reordered.png"), 1100))
    page.progress.show()
    page.progress.setValue(620)
    page.start_button.setText(i18n.t("common.working"))
    page.start_button.setEnabled(False)
    frames.append((grab(window, shots / "_merge-running.png"), 700))
    page.progress.hide()
    page.start_button.setEnabled(True)
    page.start_button.setText(i18n.t("common.start"))
    page.start()
    merged = grab(window, shots / "merge.png")
    frames.append((merged, 2200))

    # extract (page grid)
    page = window.open_tool("extract")
    page.add_files([str(docs["report"])])
    settle()
    page.grid.set_selected_indices([0, 2, 3, 5])
    frames.append((grab(window, shots / "extract.png"), 2000))

    # compress
    page = window.open_tool("compress")
    page.add_files([str(docs["report"]), str(docs["brochure"])])
    page.start()
    grab(window, shots / "compress.png")

    # watermark preview
    page = window.open_tool("watermark")
    page.add_files([str(docs["report"])])
    settle()
    page.tool.text.setText("CONFIDENTIAL")
    page.tool.opacity.setValue(55)
    page.tool.size.setValue(72)
    page.tool.color = "#ffffff"
    page.tool._paint_color_button()
    page.tool.tiled.setChecked(True)
    grab(window, shots / "watermark.png")

    # images to pdf
    page = window.open_tool("img2pdf")
    page.add_files([str(p) for p in photos])
    grab(window, shots / "images-to-pdf.png")

    # info
    page = window.open_tool("info")
    page.add_files([str(docs["report"])])
    settle()
    grab(window, shots / "info.png")
    window.close()

    # ---- Dark theme
    window = new_window(settings, "en", "dark")
    dark_home = grab(window, shots / "home-dark.png")
    page = window.open_tool("reorder")
    page.add_files([str(docs["report"])])
    settle()
    page.grid.set_order([0, 3, 1, 2, 4, 5, 6, 7])
    grab(window, shots / "reorder-dark.png")
    window.close()

    # ---- Turkish
    window = new_window(settings, "tr", "light")
    grab(window, shots / "home-tr.png")
    page = window.open_tool("delete")
    page.add_files([str(docs["report"])])
    settle()
    page.grid.set_selected_indices([1, 6])
    grab(window, shots / "delete-tr.png")
    window.close()
    frames.append((dark_home, 1800))

    # ---- GIF
    width = 960
    gif_frames = []
    durations = []
    for image, duration in frames:
        height = int(image.height * width / image.width)
        small = image.resize((width, height), Image.LANCZOS)
        gif_frames.append(small.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
        durations.append(duration)
    gif_path = out / "demo.gif"
    gif_frames[0].save(gif_path, save_all=True, append_images=gif_frames[1:], duration=durations, loop=0, optimize=True)
    for temp in shots.glob("_*.png"):
        temp.unlink()
    print("screenshots:", sorted(p.name for p in shots.glob("*.png")))
    print("gif:", gif_path, gif_path.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
