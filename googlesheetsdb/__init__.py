"""Use a Google Sheet as a small database table with SQL-like queries."""
from .database import SCOPES, GoogleSheetDB

__all__ = ["GoogleSheetDB", "SCOPES"]
