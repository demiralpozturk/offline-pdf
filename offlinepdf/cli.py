"""Command-line interface: every tool, scriptable.

Examples:
    offlinepdf-cli merge a.pdf b.pdf -o merged.pdf
    offlinepdf-cli compress big.pdf --level high
    offlinepdf-cli pdf2images slides.pdf --format jpg --dpi 200
    offlinepdf-cli info report.pdf --json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__, core
from .core.document import unique_path
from .core.overlay import POSITIONS


def _expand(patterns: list[str]) -> list[Path]:
    """Expand wildcards ourselves: Windows shells do not."""
    files: list[Path] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern)) if any(ch in pattern for ch in "*?[") else [pattern]
        if not matches:
            raise SystemExit(f"error: no files match {pattern}")
        files.extend(Path(m) for m in matches)
    return files


def _out_file(args, source: Path, suffix: str) -> Path:
    if args.output:
        return Path(args.output)
    return unique_path(source.parent, source.stem, suffix)


def _out_dir(args, source: Path, suffix: str) -> Path:
    return Path(args.output) if args.output else source.parent / f"{source.stem}{suffix}"


def _parse_order(text: str, path: Path, password: str | None) -> list[int]:
    count = core.page_count(path, password)
    return core.parse_selection(text, count)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="offlinepdf-cli",
        description="OfflinePDF command line. Everything runs locally; nothing is uploaded.",
    )
    parser.add_argument("--version", action="version", version=f"OfflinePDF {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def command(name: str, help_text: str, *, many: bool = False, output_help: str = "output file") -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument("inputs" if many else "input", nargs="+" if many else None, help="input file(s)")
        p.add_argument("-o", "--output", help=output_help)
        p.add_argument("--password", help="password of a protected input PDF")
        return p

    p = command("merge", "Combine PDFs in the given order.", many=True)
    p.add_argument("--no-bookmarks", action="store_true", help="don't add a bookmark per file")
    p.add_argument("--drop-outlines", action="store_true", help="drop the inputs' own bookmarks")

    p = command("split", "Split into single pages, chunks or ranges.", output_help="output folder")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--every", type=int, help="pages per file")
    group.add_argument("--ranges", help='one file per range, e.g. "1-3, 4-6, 7-"')

    p = command("extract", "Copy selected pages into a new PDF.")
    p.add_argument("--pages", required=True, help='e.g. "1-3, 5, 8-"')

    p = command("delete", "Remove selected pages.")
    p.add_argument("--pages", required=True, help='e.g. "2, 4-5"')

    p = command("reorder", "Write pages in a new order.")
    p.add_argument("--order", required=True, help='e.g. "3, 1, 2, 4-" or "end-1" to reverse')

    p = command("rotate", "Rotate pages clockwise.")
    p.add_argument("--angle", type=int, choices=(90, 180, 270), default=90)
    p.add_argument("--pages", default="", help="pages to rotate (default: all)")

    p = command("compress", "Make a PDF smaller.")
    p.add_argument("-l", "--level", choices=("low", "medium", "high"), default="medium")

    p = command("images2pdf", "Turn images into one PDF.", many=True)
    p.add_argument("--page-size", choices=("fit", "a4", "letter"), default="fit")
    p.add_argument("--margin", type=float, default=0, help="margin in mm")

    p = command("pdf2images", "Render pages to PNG or JPG.", output_help="output folder")
    p.add_argument("--format", choices=("png", "jpg"), default="png")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--quality", type=int, default=90, help="JPG quality")
    p.add_argument("--pages", default="")

    p = command("watermark", "Stamp text on pages.")
    p.add_argument("--text", required=True)
    p.add_argument("--size", type=float, default=60, help="font size in points")
    p.add_argument("--color", default="#d32f2f")
    p.add_argument("--opacity", type=float, default=0.3, help="0.02 - 1.0")
    p.add_argument("--angle", type=float, default=45)
    p.add_argument("--tiled", action="store_true")
    p.add_argument("--under", action="store_true", help="place behind the content")
    p.add_argument("--pages", default="")

    p = command("numbers", "Add page numbers.")
    p.add_argument("--position", choices=POSITIONS, default="bottom-center")
    p.add_argument("--format", dest="template", default="{n} / {total}", help="{n} and {total} are replaced")
    p.add_argument("--start", type=int, default=1)
    p.add_argument("--size", type=float, default=11)
    p.add_argument("--skip-first", action="store_true")

    p = command("protect", "Encrypt with a password (AES-256).")
    p.add_argument("--new-password", required=True, help="password needed to open the output")
    p.add_argument("--no-print", action="store_true")
    p.add_argument("--no-copy", action="store_true")
    p.add_argument("--allow-edit", action="store_true")

    p = command("unlock", "Remove a known password.")

    p = command("metadata", "Edit or strip document properties.")
    for name in ("title", "author", "subject", "keywords", "creator", "producer"):
        p.add_argument(f"--{name}")
    p.add_argument("--strip", action="store_true", help="remove all metadata")

    p = command("info", "Print a summary of a PDF.")
    p.add_argument("--json", action="store_true")
    return parser


def run(args) -> list[Path] | None:
    cmd = args.command
    pw = args.password
    if cmd in ("merge", "images2pdf"):
        inputs = _expand(args.inputs)
        if cmd == "merge":
            dst = Path(args.output) if args.output else unique_path(inputs[0].parent, "merged")
            passwords = {str(p): pw for p in inputs} if pw else None
            core.merge(inputs, dst, bookmarks=not args.no_bookmarks, keep_outlines=not args.drop_outlines, passwords=passwords)
        else:
            dst = Path(args.output) if args.output else unique_path(inputs[0].parent, "images")
            core.images_to_pdf(inputs, dst, page_size=args.page_size, margin_mm=args.margin)
        return [dst]

    src = Path(args.input)
    if cmd == "split":
        mode = "ranges" if args.ranges else "every" if args.every else "each"
        return core.split(src, _out_dir(args, src, "_split"), mode=mode, every=args.every or 1, ranges=args.ranges or "", password=pw)
    if cmd == "extract":
        return [core.extract(src, _out_file(args, src, "_extract"), args.pages, password=pw)]
    if cmd == "delete":
        return [core.delete(src, _out_file(args, src, "_edited"), args.pages, password=pw)]
    if cmd == "reorder":
        order = _parse_order(args.order, src, pw)
        return [core.reorder(src, _out_file(args, src, "_reordered"), order, password=pw)]
    if cmd == "rotate":
        return [core.rotate(src, _out_file(args, src, "_rotated"), args.angle, pages=args.pages, password=pw)]
    if cmd == "compress":
        result = core.compress(src, _out_file(args, src, "_compressed"), level=args.level, password=pw)
        print(f"{result.original_size:,} -> {result.new_size:,} bytes ({result.saved_percent:.0f}% smaller)")
        return [result.path]
    if cmd == "pdf2images":
        return core.pdf_to_images(
            src, _out_dir(args, src, "_images"), fmt=args.format, dpi=args.dpi, quality=args.quality, pages=args.pages, password=pw
        )
    if cmd == "watermark":
        return [
            core.watermark(
                src,
                _out_file(args, src, "_watermarked"),
                args.text,
                font_size=args.size,
                color=args.color,
                opacity=args.opacity,
                angle=args.angle,
                tiled=args.tiled,
                under=args.under,
                pages=args.pages,
                password=pw,
            )
        ]
    if cmd == "numbers":
        return [
            core.page_numbers(
                src,
                _out_file(args, src, "_numbered"),
                position=args.position,
                template=args.template,
                start=args.start,
                font_size=args.size,
                skip_first=args.skip_first,
                password=pw,
            )
        ]
    if cmd == "protect":
        return [
            core.protect(
                src,
                _out_file(args, src, "_protected"),
                args.new_password,
                allow_print=not args.no_print,
                allow_copy=not args.no_copy,
                allow_modify=args.allow_edit,
                password=pw,
            )
        ]
    if cmd == "unlock":
        if not pw:
            raise SystemExit("error: unlock needs --password")
        return [core.unlock(src, _out_file(args, src, "_unlocked"), pw)]
    if cmd == "metadata":
        if args.strip:
            return [core.strip_metadata(src, _out_file(args, src, "_clean"), password=pw)]
        values = {
            name: getattr(args, name)
            for name in ("title", "author", "subject", "keywords", "creator", "producer")
            if getattr(args, name) is not None
        }
        if not values:
            raise SystemExit("error: give at least one field (e.g. --title) or --strip")
        current = core.read_metadata(src, pw)
        current.update(values)
        return [core.set_metadata(src, _out_file(args, src, "_edited"), current, password=pw)]
    if cmd == "info":
        info = core.get_info(src, pw)
        if args.json:
            data = asdict(info)
            data["path"] = str(info.path)
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(f"File:        {info.path.name}")
            print(f"Size:        {info.file_size:,} bytes")
            print(f"Pages:       {info.pages}")
            print(f"PDF version: {info.version}")
            print(f"Encrypted:   {'yes' if info.encrypted else 'no'}")
            for label, count in info.page_sizes:
                print(f"Page size:   {label} x{count}")
            print(f"Text layer:  {'yes' if info.has_text else 'no (scanned?)'}")
            print(f"Images:      {info.images}")
            print(f"Bookmarks:   {info.bookmarks}")
            for key, value in info.metadata.items():
                if value:
                    print(f"{key.capitalize() + ':':<13}{value}")
        return None
    raise SystemExit(f"unknown command {cmd}")


def main(argv: list[str] | None = None) -> int:
    # Windows consoles may not be UTF-8; never crash on printing a file name.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass
    args = build_parser().parse_args(argv)
    try:
        outputs = run(args)
    except core.OfflinePDFError as exc:
        print(f"error: {exc.code.split('.', 1)[1].replace('_', ' ')}: {exc.detail}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for path in outputs or []:
        print(os.fspath(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
