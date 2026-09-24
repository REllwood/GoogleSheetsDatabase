"""
Reads a worksheet as a database table and evaluates WHERE conditions against its rows.

A table is one worksheet (tab). Row 1 holds the column names; every row below it is a
record. Completely empty rows are skipped.
"""
from gspread.utils import numericise_all

from .errors import ColumnNotFoundError, QueryError, TableNotFoundError
from .query_parser import And, Comparison, IsNull, Not, Or

HEADER_ROW = 1


def open_table(spreadsheet, name):
    """
    Finds the worksheet called `name` and reads all of its values in one request.

    The name is matched exactly first, then ignoring case and surrounding spaces.

    Raises:
    - TableNotFoundError: If no worksheet has that name.
    """
    worksheets = spreadsheet.worksheets()
    matches = [w for w in worksheets if w.title == name]
    if not matches:
        matches = [w for w in worksheets if _fold(w.title) == _fold(name)]
    if not matches:
        titles = ", ".join(repr(w.title) for w in worksheets)
        raise TableNotFoundError(f"No worksheet is named {name!r}. Worksheets: {titles}")
    if len(matches) > 1:
        raise TableNotFoundError(f"More than one worksheet matches {name!r}; use its exact name")
    worksheet = matches[0]
    return Table(worksheet, _read_values(worksheet))


class Table:
    def __init__(self, worksheet, values):
        self.worksheet = worksheet
        self.header = [_header_name(v) for v in values[0]] if values else []
        self.width = len(self.header)
        self.rows = []  # (sheet row number, values padded to the header's width)
        for offset, row in enumerate(values[1:]):
            if any(not _is_blank(v) for v in row):
                row = list(row[:self.width]) + [""] * (self.width - len(row))
                self.rows.append((HEADER_ROW + 1 + offset, row))

        named = [n for n in self.header if n]
        duplicates = sorted({n for n in named if named.count(n) > 1})
        if duplicates:
            raise QueryError(
                f"The header row of {self.title!r} repeats the column name(s) "
                f"{', '.join(map(repr, duplicates))}; each column needs a unique name"
            )

    @property
    def title(self):
        return self.worksheet.title

    @property
    def named_columns(self):
        """Indexes of the columns that have a name in the header row."""
        return [i for i, name in enumerate(self.header) if name]

    def require_header(self):
        """Raises ColumnNotFoundError if the header row has no column names."""
        if not self.named_columns:
            raise ColumnNotFoundError(
                f"{self.title!r} has no header row; put the column names in row {HEADER_ROW}"
            )

    def column_index(self, name):
        """
        Finds a column by name: exactly first, then ignoring case and surrounding spaces.

        Raises:
        - ColumnNotFoundError: If no column (or more than one) matches.
        """
        self.require_header()
        if name in self.header:
            return self.header.index(name)
        matches = [i for i, column in enumerate(self.header) if column and _fold(column) == _fold(name)]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise ColumnNotFoundError(f"More than one column of {self.title!r} matches {name!r}; use its exact name")
        columns = ", ".join(repr(self.header[i]) for i in self.named_columns)
        raise ColumnNotFoundError(f"{self.title!r} has no column {name!r}. Columns: {columns}")

    def column_indexes(self, names):
        """Resolves several column names, rejecting any column named twice."""
        indexes = [self.column_index(name) for name in names]
        seen = set()
        for name, index in zip(names, indexes):
            if index in seen:
                raise QueryError(f"Column {self.header[index]!r} is listed more than once")
            seen.add(index)
        return indexes

    def matching_rows(self, condition):
        """Returns the (sheet row number, values) of every row that meets the condition."""
        if condition is None:
            return list(self.rows)
        predicate = self._compile(condition)
        return [(number, row) for number, row in self.rows if predicate(row)]

    def record(self, row, indexes=None):
        """Turns a row into a {column name: value} dict, for the given column indexes."""
        if indexes is None:
            indexes = self.named_columns
        values = numericise_all([row[i] for i in indexes])
        return {self.header[i]: value for i, value in zip(indexes, values)}

    def _compile(self, condition):
        """Turns a parsed condition into a function of a row, resolving columns once."""
        if isinstance(condition, And):
            left, right = self._compile(condition.left), self._compile(condition.right)
            return lambda row: left(row) and right(row)
        if isinstance(condition, Or):
            left, right = self._compile(condition.left), self._compile(condition.right)
            return lambda row: left(row) or right(row)
        if isinstance(condition, Not):
            inner = self._compile(condition.condition)
            return lambda row: not inner(row)
        if isinstance(condition, IsNull):
            index = self.column_index(condition.column)
            return lambda row: _is_blank(row[index]) != condition.negated
        if isinstance(condition, Comparison):
            index = self.column_index(condition.column)
            return lambda row: _compare(row[index], condition.operator, condition.value)
        raise TypeError(f"Unknown condition {condition!r}")


def _read_values(worksheet):
    return worksheet.get_values()


def _header_name(value):
    return str(value).strip()


def _fold(name):
    return name.strip().casefold()


def _is_blank(value):
    return value == "" or value is None


def _compare(cell, operator, value):
    """
    Compares a cell with a value from the query.

    NULL compares with blank cells: `= NULL` matches them and `!= NULL` matches the rest.
    Otherwise a blank cell, or a cell whose type can't be compared with the value, is
    only ever "not equal" to it.
    """
    if value is None:
        if operator == "=":
            return _is_blank(cell)
        if operator == "!=":
            return not _is_blank(cell)
        return False

    order = _order(cell, value)
    if order is None:
        return operator == "!="
    return {
        "=": order == 0,
        "!=": order != 0,
        "<": order < 0,
        "<=": order <= 0,
        ">": order > 0,
        ">=": order >= 0,
    }[operator]


def _order(cell, value):
    """Returns -1, 0 or 1 as the cell is less than, equal to or greater than the value,
    or None when they can't be compared."""
    if _is_blank(cell):
        return None
    if isinstance(value, bool):
        text = str(cell).strip().upper()
        if text not in ("TRUE", "FALSE"):
            return None
        cell = text == "TRUE"
    elif isinstance(value, (int, float)):
        try:
            cell = float(str(cell).strip())
        except ValueError:
            return None
    else:
        cell = str(cell)
    return (cell > value) - (cell < value)
