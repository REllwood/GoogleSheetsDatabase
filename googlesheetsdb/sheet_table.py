"""
Reads a worksheet as a database table and evaluates WHERE conditions against its rows.

A table is one worksheet (tab). Row 1 holds the column names; every row below it is a
record. Completely empty rows are skipped.

Cells are read as their underlying values rather than as displayed: numbers come back as
int or float (so 50% is 0.5), checkboxes and TRUE/FALSE as bool, text as str exactly as
stored (so a postcode such as '0800' keeps its leading zero), and blank cells as None.
Dates and times come back as text, formatted as they are in the sheet.
"""
import math
import re

from gspread.utils import DateTimeOption, ValueRenderOption

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
        return {self.header[i]: None if _is_blank(row[i]) else row[i] for i in indexes}

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
    values = worksheet.get_values(
        value_render_option=ValueRenderOption.unformatted,
        date_time_render_option=DateTimeOption.formatted_string,
    )
    return [[_whole_number_as_int(v) for v in row] for row in values]


def _whole_number_as_int(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _header_name(value):
    return _as_text(value).strip()


def _as_text(value):
    """Writes a value the way the sheet displays it by default."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)


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


_NUMBER_TEXT = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")


def _order(cell, value):
    """
    Returns -1, 0 or 1 as the cell is less than, equal to or greater than the value, or
    None when they can't be compared.

    Values of the same type compare naturally: numbers numerically, text by character
    (case-sensitive), TRUE/FALSE with each other. Text and numbers compare only when the
    text is written exactly like a number, such as '38' or '-2.5'; text such as '0800' or
    '1e3' never equals a number.
    """
    if _is_blank(cell):
        return None
    if isinstance(cell, bool) or isinstance(value, bool):
        if not (isinstance(cell, bool) and isinstance(value, bool)):
            return None
    elif isinstance(cell, str) and not isinstance(value, str):
        cell = _number_from_text(cell)
    elif isinstance(value, str) and not isinstance(cell, str):
        value = _number_from_text(value)
    if cell is None or value is None:
        return None
    return (cell > value) - (cell < value)


def _number_from_text(text):
    """The number that `text` spells out exactly, such as 38 for '38', otherwise None."""
    text = text.strip()
    if not _NUMBER_TEXT.fullmatch(text):
        return None
    number = float(text)
    if not math.isfinite(number):
        return None
    return _whole_number_as_int(number)
