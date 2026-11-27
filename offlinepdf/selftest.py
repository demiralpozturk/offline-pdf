"""Headless end-to-end self-test, also used to verify the packaged .exe.

    OfflinePDF.exe --selftest <folder>

Runs every tool on generated documents, builds the whole UI offscreen,
writes <folder>/report.json and <folder>/home.png, and exits with 0 (all
passed) or 1. Nothing is shown on screen and nothing touches the network.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path


def run_selftest(target: str | None = None) -> int:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    out = Path(target) if target else Path(tempfile.mkdtemp(prefix="offlinepdf-selftest-"))
    out.mkdir(parents=True, exist_ok=True)
    work = out / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    checks: list[dict] = []

    def check(name: str, fn) -> None:
        started = time.perf_counter()
        try:
            detail = fn()
            checks.append({"name": name, "ok": True, "detail": detail or "", "seconds": round(time.perf_counter() - started, 2)})
        except Exception as exc:  # report everything, keep going
            checks.append(
                {
                    "name": name,
                    "ok": False,
                    "detail": f"{exc.__class__.__name__}: {exc}",
                    "trace": traceback.format_exc(),
                    "seconds": round(time.perf_counter() - started, 2),
                }
            )

    from . import __version__, core, samples

    docs: dict = {}
    photos: list = []

    def make_samples():
        docs.update(samples.make_all(work / "in"))
        photos.extend(samples.photo_files(work / "in" / "photos", 2))
        return ", ".join(p.name for p in docs.values())

    check("samples", make_samples)
    report, invoice, brochure = docs.get("report"), docs.get("invoice"), docs.get("brochure")
    res = work / "out"

    def expect(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    def merge():
        dst = core.merge([report, invoice, brochure], res / "merged.pdf")
        expect(core.page_count(dst) == 12, "merged page count")
        return "12 pages"

    def split():
        parts = core.split(report, res / "split", mode="every", every=3)
        expect(len(parts) == 3, "3 parts")
        return f"{len(parts)} files"

    def extract_delete_reorder_rotate():
        core.extract(report, res / "extract.pdf", "1, 3-4")
        expect(core.page_count(res / "extract.pdf") == 3, "extract")
        core.delete(report, res / "delete.pdf", "2")
        expect(core.page_count(res / "delete.pdf") == 7, "delete")
        core.reorder(report, res / "reorder.pdf", [7, 6, 5, 4, 3, 2, 1, 0])
        core.rotate(report, res / "rotate.pdf", 90, pages="1")
        return "ok"

    def compress():
        result = core.compress(report, res / "compressed.pdf", level="high")
        return f"{result.original_size} -> {result.new_size} bytes"

    def convert():
        images = core.pdf_to_images(invoice, res / "images", fmt="jpg", dpi=100)
        pdf = core.images_to_pdf(photos + images, res / "from-images.pdf", page_size="a4", margin_mm=10)
        expect(core.page_count(pdf) == len(photos) + len(images), "images to pdf")
        return f"{len(images)} image(s) and back"

    def overlays():
        marked = core.watermark(report, res / "watermark.pdf", "GİZLİDİR", tiled=True)
        expect("GİZLİDİR" in core.render.page_text(marked, 1), "watermark text")
        numbered = core.page_numbers(report, res / "numbers.pdf")
        expect("2 / 8" in core.render.page_text(numbered, 1), "page number text")
        return "ok"

    def security():
        locked = core.protect(invoice, res / "protected.pdf", "s3cret")
        expect(core.is_encrypted(locked), "encrypted")
        opened = core.unlock(locked, res / "unlocked.pdf", "s3cret")
        expect(not core.is_encrypted(opened), "decrypted")
        return "AES-256 round trip"

    def metadata():
        edited = core.set_metadata(invoice, res / "meta.pdf", {"title": "Self-test", "author": "OfflinePDF"})
        expect(core.read_metadata(edited)["title"] == "Self-test", "title")
        clean = core.strip_metadata(edited, res / "clean.pdf")
        expect(not any(core.read_metadata(clean).values()), "stripped")
        info = core.get_info(report)
        return f"{info.pages} pages, {info.images} images"

    if docs:
        for name, fn in (
            ("merge", merge),
            ("split", split),
            ("extract/delete/reorder/rotate", extract_delete_reorder_rotate),
            ("compress", compress),
            ("convert", convert),
            ("watermark/page numbers", overlays),
            ("protect/unlock", security),
            ("metadata/info", metadata),
        ):
            check(name, fn)

    def ui():
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication

        from .app import create_app
        from .ui import worker
        from .ui.main_window import MainWindow
        from .ui.tools import ALL_TOOLS

        create_app([sys.argv[0]])
        settings = QSettings(str(work / "settings.ini"), QSettings.IniFormat)
        window = MainWindow(settings)
        window.resize(1280, 820)
        window.show()
        for cls in ALL_TOOLS:
            window.open_tool(cls.id)
        page = window.open_tool("extract")
        page.add_files([str(report)])
        for _ in range(5):
            worker.wait_all(10000)
            QApplication.processEvents()
        window.show_home()
        QApplication.processEvents()
        window.grab().save(str(out / "home.png"))
        window.close()
        worker.shutdown()
        window.deleteLater()
        QApplication.processEvents()
        return f"{len(ALL_TOOLS)} tool pages built"

    check("ui", ui)

    ok = all(item["ok"] for item in checks)
    report_data = {
        "ok": ok,
        "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0],
        "checks": checks,
    }
    (out / "report.json").write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    if sys.stdout is not None:
        for item in checks:
            print(("PASS" if item["ok"] else "FAIL"), item["name"], "-", item["detail"])
        print("RESULT:", "OK" if ok else "FAILED", "->", out / "report.json")
    return 0 if ok else 1
