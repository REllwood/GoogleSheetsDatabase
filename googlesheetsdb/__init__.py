"""Use a Google Sheet as a small database table with SQL-like queries."""
from .database import SCOPES, GoogleSheetDB
from .errors import ColumnNotFoundError, QueryError, QuerySyntaxError, TableNotFoundError

__all__ = [
    "GoogleSheetDB",
    "SCOPES",
    "QueryError",
    "QuerySyntaxError",
    "TableNotFoundError",
    "ColumnNotFoundError",
]
