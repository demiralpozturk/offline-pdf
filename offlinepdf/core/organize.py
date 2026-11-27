"""Merge, split, extract, delete, reorder and rotate pages."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Sequence

import pikepdf
from pypdf import PdfReader, PdfWriter

from .document import Progress, open_pdf, report, save_pdf, unique_path
from .errors import InvalidRangeError, NothingToDoError
from .pages import parse_ranges, parse_selection


def _normalized_bytes(path: str | os.PathLike, password: str | None) -> io.BytesIO:
    """Decrypt and repair a PDF with qpdf, returning clean bytes for pypdf."""
    buffer = io.BytesIO()
    with open_pdf(path, password) as pdf:
        pdf.save(buffer)
    buffer.seek(0)
    return buffer


def merge(
    sources: Sequence[str | os.PathLike],
    dst: str | os.PathLike,
    *,
    bookmarks: bool = True,
    keep_outlines: bool = True,
    passwords: dict[str, str] | None = None,
    progress: Progress = None,
) -> Path:
    """Join several PDFs into one, in the given order.

    With ``bookmarks`` each source file gets a bookmark (named after the file)
    and its own bookmarks are nested under it when ``keep_outlines`` is set.
    """
    if len(sources) < 1:
        raise NothingToDoError("merge needs at least one file")
    passwords = passwords or {}
    writer = PdfWriter()
    total = len(sources)
    for done, src in enumerate(sources):
        data = _normalized_bytes(src, passwords.get(os.fspath(src)))
        reader = PdfReader(data)
        title = Path(src).stem if bookmarks else None
        writer.append(reader, outline_item=title, import_outline=keep_outlines)
        report(progress, done + 1, total + 1)
    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    # Re-save through qpdf: smaller files (object streams) and a sanity check.
    with pikepdf.open(buffer) as merged:
        out = save_pdf(merged, dst)
    report(progress, total + 1, total + 1)
    return out


def _copy_pages(src_pdf: pikepdf.Pdf, indices: Sequence[int], dst: str | os.PathLike) -> Path:
    with pikepdf.new() as out:
        for index in indices:
            out.pages.append(src_pdf.pages[index])
        _copy_document_info(src_pdf, out)
        return save_pdf(out, dst)


def _copy_document_info(src_pdf: pikepdf.Pdf, out: pikepdf.Pdf) -> None:
    try:
        if "/Info" in src_pdf.trailer:
            out.docinfo = out.copy_foreign(src_pdf.trailer.Info)
    except Exception:  # metadata is a nice-to-have, never fail because of it
        pass


def split(
    src: str | os.PathLike,
    out_dir: str | os.PathLike,
    *,
    mode: str = "each",
    ranges: str = "",
    every: int = 1,
    password: str | None = None,
    progress: Progress = None,
) -> list[Path]:
    """Split a PDF into several files.

    mode="each":   one file per page
    mode="every":  chunks of ``every`` pages
    mode="ranges": one file per comma-separated range, e.g. "1-3, 4-6, 7-"
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(src).stem
    outputs: list[Path] = []
    with open_pdf(src, password) as pdf:
        count = len(pdf.pages)
        if mode == "ranges":
            groups = parse_ranges(ranges, count)
        elif mode == "every":
            size = max(1, int(every))
            groups = [list(range(i, min(i + size, count))) for i in range(0, count, size)]
        else:
            groups = [[i] for i in range(count)]
        width = max(3, len(str(count)))
        for done, group in enumerate(groups):
            if len(group) == 1:
                label = f"_page{group[0] + 1:0{width}d}"
            else:
                label = f"_pages{group[0] + 1}-{group[-1] + 1}"
            outputs.append(_copy_pages(pdf, group, unique_path(out_dir, stem, label)))
            report(progress, done + 1, len(groups))
    return outputs


def extract(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    pages: str,
    *,
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    """Copy the selected pages (in the typed order) into a new PDF."""
    with open_pdf(src, password) as pdf:
        indices = parse_selection(pages, len(pdf.pages))
        out = _copy_pages(pdf, indices, dst)
    report(progress, 1, 1)
    return out


def delete(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    pages: str,
    *,
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    """Remove the selected pages and keep the rest."""
    with open_pdf(src, password) as pdf:
        count = len(pdf.pages)
        remove = set(parse_selection(pages, count))
        keep = [i for i in range(count) if i not in remove]
        if not keep:
            raise InvalidRangeError(pages, page_count=count)
        out = _copy_pages(pdf, keep, dst)
    report(progress, 1, 1)
    return out


def reorder(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    order: Sequence[int],
    *,
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    """Write pages in ``order`` (0-based indices). Pages left out are dropped."""
    with open_pdf(src, password) as pdf:
        count = len(pdf.pages)
        if not order or any(i < 0 or i >= count for i in order):
            raise InvalidRangeError(",".join(str(i + 1) for i in order), page_count=count)
        out = _copy_pages(pdf, list(order), dst)
    report(progress, 1, 1)
    return out


def rotate(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    angle: int,
    *,
    pages: str = "",
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    """Rotate pages clockwise by 90, 180 or 270 degrees (all pages if ``pages`` is empty)."""
    if angle % 90 != 0:
        raise ValueError("angle must be a multiple of 90")
    with open_pdf(src, password) as pdf:
        count = len(pdf.pages)
        targets = parse_selection(pages, count) if pages.strip() else range(count)
        targets = list(targets)
        for done, index in enumerate(targets):
            pdf.pages[index].rotate(angle, relative=True)
            report(progress, done + 1, len(targets))
        return save_pdf(pdf, dst)
