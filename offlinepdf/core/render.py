"""Rendering pages with PDFium (pypdfium2).

PDFium is not thread-safe, so every call goes through one global lock.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager

import pypdfium2 as pdfium
from PIL import Image

from .errors import InvalidPdfError, PasswordRequiredError, WrongPasswordError

PDFIUM_LOCK = threading.RLock()


@contextmanager
def open_document(path: str | os.PathLike, password: str | None = None):
    with PDFIUM_LOCK:
        try:
            doc = pdfium.PdfDocument(os.fspath(path), password=password or None)
        except pdfium.PdfiumError as exc:
            message = str(exc).lower()
            if "password" in message:
                if password:
                    raise WrongPasswordError(str(path)) from exc
                raise PasswordRequiredError(str(path)) from exc
            raise InvalidPdfError(f"{path}: {exc}") from exc
        try:
            yield doc
        finally:
            doc.close()


def render_page(doc: pdfium.PdfDocument, index: int, *, dpi: float = 72, max_px: int | None = None) -> Image.Image:
    with PDFIUM_LOCK:
        page = doc[index]
        try:
            width, height = page.get_size()
            scale = dpi / 72.0
            if max_px:
                scale = min(scale, max_px / max(width, height, 1))
            bitmap = page.render(scale=scale, may_draw_forms=True)
            image = bitmap.to_pil()
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            return image
        finally:
            page.close()


def thumbnail(path: str | os.PathLike, index: int = 0, max_px: int = 160, password: str | None = None) -> Image.Image:
    with open_document(path, password) as doc:
        return render_page(doc, index, dpi=72, max_px=max_px)


def page_text(path: str | os.PathLike, index: int, password: str | None = None) -> str:
    with open_document(path, password) as doc:
        with PDFIUM_LOCK:
            page = doc[index]
            try:
                textpage = page.get_textpage()
                try:
                    return textpage.get_text_range()
                finally:
                    textpage.close()
            finally:
                page.close()
