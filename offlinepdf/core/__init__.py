"""Pure-Python PDF operations used by the GUI, the CLI and the tests.

Nothing in this package touches the network.
"""

from .convert import images_to_pdf, pdf_to_images
from .document import page_count, unique_path
from .errors import (
    InvalidImageError,
    InvalidPdfError,
    InvalidRangeError,
    NothingToDoError,
    OfflinePDFError,
    PasswordRequiredError,
    WrongPasswordError,
)
from .metadata import get_info, read_metadata, set_metadata, strip_metadata
from .optimize import CompressResult, compress
from .organize import delete, extract, merge, reorder, rotate, split
from .overlay import page_numbers, watermark
from .pages import format_selection, parse_ranges, parse_selection
from .security import is_encrypted, protect, unlock

__all__ = [
    "CompressResult",
    "InvalidImageError",
    "InvalidPdfError",
    "InvalidRangeError",
    "NothingToDoError",
    "OfflinePDFError",
    "PasswordRequiredError",
    "WrongPasswordError",
    "compress",
    "delete",
    "extract",
    "format_selection",
    "get_info",
    "images_to_pdf",
    "is_encrypted",
    "merge",
    "page_count",
    "page_numbers",
    "parse_ranges",
    "parse_selection",
    "pdf_to_images",
    "protect",
    "read_metadata",
    "reorder",
    "rotate",
    "set_metadata",
    "split",
    "strip_metadata",
    "unique_path",
    "unlock",
    "watermark",
]
