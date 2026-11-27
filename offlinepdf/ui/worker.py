"""Run slow work off the UI thread."""

from __future__ import annotations

import traceback
from typing import Callable

from PySide6.QtCore import QCoreApplication, QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage
from PIL import Image

# Tool jobs and thumbnail jobs get their own pools so a long render queue
# never blocks a tool from starting (PDFium itself is serialized). The pools
# are children of the QApplication so Qt tears them down in the right order.
_pools: dict[str, QThreadPool] = {}
_alive: set["JobSignals"] = set()


def _pool(name: str) -> QThreadPool:
    pool = _pools.get(name)
    if pool is None:
        pool = QThreadPool(QCoreApplication.instance())
        pool.setMaxThreadCount(1)
        _pools[name] = pool
    return pool


def tool_pool() -> QThreadPool:
    return _pool("tool")


def thumb_pool() -> QThreadPool:
    return _pool("thumb")


def wait_all(msecs: int = 30000) -> None:
    for pool in list(_pools.values()):
        pool.waitForDone(msecs)


def shutdown() -> None:
    """Drop queued jobs and wait for running ones; call before the app exits."""
    for pool in list(_pools.values()):
        pool.clear()
        pool.waitForDone(15000)
    _pools.clear()


class JobSignals(QObject):
    progress = Signal(int, int)
    finished = Signal(object)
    failed = Signal(object)


class Job(QRunnable):
    """Runs ``fn(progress)`` in a pool; results come back as Qt signals."""

    def __init__(self, fn: Callable):
        super().__init__()
        self.fn = fn
        self.signals = JobSignals()
        _alive.add(self.signals)
        self.signals.finished.connect(lambda *_: _alive.discard(self.signals))
        self.signals.failed.connect(lambda *_: _alive.discard(self.signals))

    def run(self) -> None:
        try:
            result = self.fn(self.signals.progress.emit)
        except Exception as exc:  # reported to the UI, never crash the app
            exc.trace = traceback.format_exc()
            self.signals.failed.emit(exc)
        else:
            self.signals.finished.emit(result)


def start(fn: Callable, *, pool: QThreadPool | None = None) -> JobSignals:
    job = Job(fn)
    (pool or tool_pool()).start(job)
    return job.signals


def pil_to_qimage(image: Image.Image) -> QImage:
    if image.mode != "RGB":
        image = image.convert("RGB")
    data = image.tobytes("raw", "RGB")
    qimage = QImage(data, image.width, image.height, image.width * 3, QImage.Format_RGB888)
    return qimage.copy()


class ThumbSignals(QObject):
    ready = Signal(str, int, QImage)
    done = Signal(str)


class ThumbnailJob(QRunnable):
    """Render page thumbnails one by one and emit each as soon as it is ready."""

    def __init__(self, token: str, path: str, indices: list[int], max_px: int, password: str | None, signals: ThumbSignals):
        super().__init__()
        self.token = token
        self.path = path
        self.indices = indices
        self.max_px = max_px
        self.password = password
        self.signals = signals
        self.cancelled = False

    def run(self) -> None:
        from ..core.render import open_document, render_page

        try:
            with open_document(self.path, self.password) as doc:
                for index in self.indices:
                    if self.cancelled:
                        return
                    image = render_page(doc, index, dpi=72, max_px=self.max_px)
                    self.signals.ready.emit(self.token, index, pil_to_qimage(image))
        except Exception:
            pass
        finally:
            if not self.cancelled:
                self.signals.done.emit(self.token)
