"""Shared helpers: opening PDFs safely, saving, output file names."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

import pikepdf

from .errors import InvalidPdfError, PasswordRequiredError, WrongPasswordError

Progress = Optional[Callable[[int, int], None]]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}


def report(progress: Progress, done: int, total: int) -> None:
    if progress is not None:
        progress(done, total)


def open_pdf(path: str | os.PathLike, password: str | None = None) -> pikepdf.Pdf:
    """Open a PDF with pikepdf, translating failures into friendly errors."""
    try:
        return pikepdf.open(os.fspath(path), password=password or "")
    except pikepdf.PasswordError as exc:
        if password:
            raise WrongPasswordError(str(path)) from exc
        raise PasswordRequiredError(str(path)) from exc
    except (pikepdf.PdfError, OSError, ValueError) as exc:
        raise InvalidPdfError(f"{path}: {exc}") from exc


def save_pdf(pdf: pikepdf.Pdf, dst: str | os.PathLike, *, compact: bool = True) -> Path:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {}
    if compact:
        kwargs["object_stream_mode"] = pikepdf.ObjectStreamMode.generate
        kwargs["compress_streams"] = True
    pdf.save(os.fspath(dst), **kwargs)
    return dst


def unique_path(folder: str | os.PathLike, stem: str, suffix: str = "", ext: str = ".pdf") -> Path:
    """Return folder/stem+suffix+ext, adding " (2)", " (3)"... if it already exists."""
    folder = Path(folder)
    candidate = folder / f"{stem}{suffix}{ext}"
    counter = 2
    while candidate.exists():
        candidate = folder / f"{stem}{suffix} ({counter}){ext}"
        counter += 1
    return candidate


def page_count(path: str | os.PathLike, password: str | None = None) -> int:
    with open_pdf(path, password) as pdf:
        return len(pdf.pages)


def is_pdf(path: str | os.PathLike) -> bool:
    return Path(path).suffix.lower() == ".pdf"


def is_image(path: str | os.PathLike) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS
