"""Make PDFs smaller.

Levels:
    "low"    lossless: rewrite streams, object streams, drop unused resources
    "medium" also re-encode large photos as JPEG (~150 DPI, quality 75)
    "high"   stronger: ~100 DPI, quality 55

Only images we can round-trip safely are touched (8-bit RGB/gray, no masks,
no Decode arrays). If the result is not smaller, the original bytes are kept.
"""

from __future__ import annotations

import io
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import pikepdf
from PIL import Image
from pikepdf import Name, PdfImage

from .document import Progress, open_pdf, report

LEVELS = {
    "low": None,
    "medium": (150, 75),
    "high": (100, 55),
}


@dataclass
class CompressResult:
    path: Path
    original_size: int
    new_size: int

    @property
    def saved_percent(self) -> float:
        if self.original_size <= 0:
            return 0.0
        return max(0.0, (1 - self.new_size / self.original_size) * 100)


def _page_long_side_inches(page: pikepdf.Page) -> float:
    box = [float(v) for v in page.mediabox]
    return max(abs(box[2] - box[0]), abs(box[3] - box[1])) / 72.0


def _recompress_image(stream: pikepdf.Object, max_px: int, quality: int) -> bool:
    for key in ("/SMask", "/Mask", "/ImageMask", "/Decode"):
        if key in stream:
            return False
    try:
        image = PdfImage(stream)
        if image.bits_per_component != 8:
            return False
        pil = image.as_pil_image()
    except Exception:
        return False
    if pil.mode not in ("RGB", "L"):
        return False
    original_bytes = len(stream.read_raw_bytes())
    width, height = pil.size
    long_side = max(width, height)
    if long_side > max_px > 0:
        scale = max_px / long_side
        pil = pil.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS)
    elif original_bytes < 20_000:
        return False  # small and not oversized: not worth touching
    buffer = io.BytesIO()
    pil.save(buffer, "JPEG", quality=quality, optimize=True)
    data = buffer.getvalue()
    if len(data) >= original_bytes:
        return False
    stream.write(data, filter=Name.DCTDecode)
    if "/DecodeParms" in stream:
        del stream["/DecodeParms"]
    stream.Width, stream.Height = pil.size
    stream.ColorSpace = Name.DeviceRGB if pil.mode == "RGB" else Name.DeviceGray
    stream.BitsPerComponent = 8
    return True


def compress(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    *,
    level: str = "medium",
    password: str | None = None,
    progress: Progress = None,
) -> CompressResult:
    if level not in LEVELS:
        raise ValueError(f"unknown level: {level}")
    src, dst = Path(src), Path(dst)
    original_size = src.stat().st_size
    settings = LEVELS[level]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open_pdf(src, password) as pdf:
        total = len(pdf.pages)
        seen: set[tuple[int, int]] = set()
        for done, page in enumerate(pdf.pages):
            if settings is not None:
                dpi, quality = settings
                max_px = int(_page_long_side_inches(page) * dpi)
                for _, stream in page.get_images().items():
                    key = stream.objgen
                    if key in seen and key != (0, 0):
                        continue
                    seen.add(key)
                    _recompress_image(stream, max_px, quality)
            try:
                page.remove_unreferenced_resources()
            except Exception:
                pass
            report(progress, done + 1, total)
        pdf.save(
            os.fspath(dst),
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            compress_streams=True,
            recompress_flate=settings is not None,
        )
    new_size = dst.stat().st_size
    if new_size >= original_size and not password:
        shutil.copyfile(src, dst)
        new_size = original_size
    return CompressResult(dst, original_size, new_size)
