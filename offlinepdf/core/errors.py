"""Errors raised by the core with a stable ``code`` the UI can translate."""

from __future__ import annotations


class OfflinePDFError(Exception):
    code = "error.generic"

    def __init__(self, detail: str = "", **params):
        super().__init__(detail or self.code)
        self.detail = detail
        self.params = params


class PasswordRequiredError(OfflinePDFError):
    code = "error.password_required"


class WrongPasswordError(OfflinePDFError):
    code = "error.wrong_password"


class InvalidRangeError(OfflinePDFError):
    code = "error.invalid_range"

    def __init__(self, spec: str = "", page_count: int | None = None):
        super().__init__(spec, spec=spec, page_count=page_count)


class InvalidPdfError(OfflinePDFError):
    code = "error.invalid_pdf"


class InvalidImageError(OfflinePDFError):
    code = "error.invalid_image"


class NothingToDoError(OfflinePDFError):
    code = "error.nothing_to_do"
