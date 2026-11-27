"""Password protection (AES-256) and removal."""

from __future__ import annotations

import os
from pathlib import Path

import pikepdf

from .document import Progress, open_pdf, report


def protect(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    user_password: str,
    *,
    owner_password: str = "",
    allow_print: bool = True,
    allow_copy: bool = True,
    allow_modify: bool = False,
    password: str | None = None,
    progress: Progress = None,
) -> Path:
    """Encrypt with AES-256. ``user_password`` is needed to open the file.

    The owner password (defaults to the user password) controls permissions.
    """
    if not user_password:
        raise ValueError("password is empty")
    permissions = pikepdf.Permissions(
        accessibility=True,
        extract=allow_copy,
        modify_annotation=allow_modify,
        modify_assembly=allow_modify,
        modify_form=allow_modify,
        modify_other=allow_modify,
        print_lowres=allow_print,
        print_highres=allow_print,
    )
    encryption = pikepdf.Encryption(
        owner=owner_password or user_password,
        user=user_password,
        R=6,
        allow=permissions,
    )
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open_pdf(src, password) as pdf:
        pdf.save(os.fspath(dst), encryption=encryption)
    report(progress, 1, 1)
    return dst


def unlock(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    password: str,
    *,
    progress: Progress = None,
) -> Path:
    """Remove the password from a PDF you know the password of."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open_pdf(src, password) as pdf:
        pdf.save(os.fspath(dst), encryption=False)
    report(progress, 1, 1)
    return dst


def is_encrypted(src: str | os.PathLike) -> bool:
    try:
        with pikepdf.open(os.fspath(src)) as pdf:
            return pdf.is_encrypted
    except pikepdf.PasswordError:
        return True
