class QueryError(Exception):
    """Base class for every problem with a query."""


class QuerySyntaxError(QueryError):
    """The query text could not be parsed, or its parameters don't fit it."""


class TableNotFoundError(QueryError):
    """No worksheet has the table name used in the query."""


class ColumnNotFoundError(QueryError):
    """A column named in the query is not in the table's header row."""
