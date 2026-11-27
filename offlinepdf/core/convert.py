"""Images -> PDF and PDF -> images."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageOps
from reportlab import rl_config
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .document import Progress, report, unique_path
from .errors import InvalidImageError, NothingToDoError
from .pages import parse_selection
from .render import open_document, render_page

rl_config.useA85 = 0  # store images as raw binary, not ASCII85 (25% smaller)

PAGE_SIZES = {"a4": A4, "letter": letter}
MM = 72 / 25.4


def _prepare_image(path: Path) -> tuple[ImageReader, tuple[int, int], float]:
    """Return a reportlab image (JPEGs are embedded as-is when possible), its pixel size and DPI."""
    try:
        with Image.open(path) as original:
            original.load()
            dpi = original.info.get("dpi", (0, 0))[0] or 0
            transposed = ImageOps.exif_transpose(original)
            unchanged = transposed.size == original.size and (
                original.getexif().get(0x0112, 1) in (1, None)
            )
            if original.format == "JPEG" and original.mode in ("RGB", "L") and unchanged:
                # Pass the original JPEG bytes through untouched: no quality loss, small file.
                return ImageReader(io.BytesIO(path.read_bytes())), original.size, float(dpi)
            image = transposed
            if getattr(image, "n_frames", 1) > 1:
                image.seek(0)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.split()[-1])
                image = background
            elif image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            buffer = io.BytesIO()
            if original.format == "JPEG":
                image.save(buffer, "JPEG", quality=92)
            else:
                image.save(buffer, "PNG")
            buffer.seek(0)
            return ImageReader(buffer), image.size, float(dpi)
    except (OSError, ValueError) as exc:
        raise InvalidImageError(f"{path}: {exc}") from exc


def images_to_pdf(
    images: Sequence[str | os.PathLike],
    dst: str | os.PathLike,
    *,
    page_size: str = "fit",
    margin_mm: float = 0,
    progress: Progress = None,
) -> Path:
    """Put each image on its own page.

    page_size: "fit" (page matches the image), "a4" or "letter"
    (orientation follows the image, the image is scaled to fit inside the margins).
    """
    if not images:
        raise NothingToDoError("no images")
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(os.fspath(dst), pageCompression=1)
    pdf.setCreator("OfflinePDF")
    margin = max(0.0, float(margin_mm)) * MM
    for done, raw_path in enumerate(images):
        reader, (px_w, px_h), dpi = _prepare_image(Path(raw_path))
        if page_size in PAGE_SIZES:
            short, long_ = sorted(PAGE_SIZES[page_size])
            page_w, page_h = (long_, short) if px_w > px_h else (short, long_)
        else:
            dpi = dpi if dpi >= 72 else 150.0
            page_w = px_w * 72.0 / dpi + 2 * margin
            page_h = px_h * 72.0 / dpi + 2 * margin
        box_w, box_h = page_w - 2 * margin, page_h - 2 * margin
        scale = min(box_w / px_w, box_h / px_h)
        draw_w, draw_h = px_w * scale, px_h * scale
        x = (page_w - draw_w) / 2
        y = (page_h - draw_h) / 2
        pdf.setPageSize((page_w, page_h))
        pdf.drawImage(reader, x, y, width=draw_w, height=draw_h)
        pdf.showPage()
        report(progress, done + 1, len(images))
    pdf.save()
    return dst


def pdf_to_images(
    src: str | os.PathLike,
    out_dir: str | os.PathLike,
    *,
    fmt: str = "png",
    dpi: int = 150,
    quality: int = 90,
    pages: str = "",
    password: str | None = None,
    progress: Progress = None,
) -> list[Path]:
    """Render pages to PNG or JPG files named <name>_page001.png, ..."""
    fmt = fmt.lower()
    if fmt in ("jpeg", "jpg"):
        fmt, ext, pil_format = "jpg", ".jpg", "JPEG"
    else:
        fmt, ext, pil_format = "png", ".png", "PNG"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(src).stem
    outputs: list[Path] = []
    with open_document(src, password) as doc:
        count = len(doc)
        indices = parse_selection(pages, count) if pages.strip() else list(range(count))
        width = max(3, len(str(count)))
        for done, index in enumerate(indices):
            image = render_page(doc, index, dpi=dpi)
            target = unique_path(out_dir, stem, f"_page{index + 1:0{width}d}", ext)
            options = {"quality": int(quality), "optimize": True} if pil_format == "JPEG" else {}
            image.save(target, pil_format, dpi=(dpi, dpi), **options)
            outputs.append(target)
            report(progress, done + 1, len(indices))
    return outputs
