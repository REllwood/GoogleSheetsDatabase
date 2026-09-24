"""Backwards compatibility: code written as `from main_module import GoogleSheetDB`
keeps working when run from a checkout of this repository.

New code should use `from googlesheetsdb import GoogleSheetDB`.
"""
from googlesheetsdb import SCOPES, GoogleSheetDB

__all__ = ["GoogleSheetDB", "SCOPES"]
