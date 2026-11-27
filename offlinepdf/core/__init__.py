"""Pure-Python PDF operations used by the GUI, the CLI and the tests.

Nothing in this package touches the network.
"""

from .errors import InvalidRangeError, OfflinePDFError
from .pages import format_selection, parse_ranges, parse_selection

__all__ = ["InvalidRangeError", "OfflinePDFError", "format_selection", "parse_ranges", "parse_selection"]
