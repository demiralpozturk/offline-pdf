from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Path to a bundled file, both from source and inside a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / relative
