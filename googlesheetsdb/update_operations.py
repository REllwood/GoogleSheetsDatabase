from gspread.utils import ValueInputOption, rowcol_to_a1

from .errors import QueryError
from .sheet_table import open_table


def execute_update(statement, sheet):
    """
    Executes an UPDATE statement on the provided Google Sheet.

    The sheet is read once, and every changed cell is written in a single request.

    Args:
    - statement (query_parser.Update): The parsed UPDATE statement.
    - sheet (gspread.Spreadsheet): The Google Sheet instance.

    Returns:
    - int: The number of rows that matched the WHERE clause and were updated.

    Raises:
    - QueryError: If the query has no WHERE clause, or sets a column twice.
    - TableNotFoundError: If no worksheet has the table's name.
    - ColumnNotFoundError: If a column isn't in the header row.
    """
    if statement.where is None:
        raise QueryError(
            "UPDATE needs a WHERE clause, so a mistake can't overwrite a whole column"
        )

    table = open_table(sheet, statement.table)
    indexes = table.column_indexes([column for column, _ in statement.assignments])
    values = ["" if value is None else value for _, value in statement.assignments]

    matching_rows = [row_number for row_number, _ in table.matching_rows(statement.where)]
    changes = [
        {"range": rowcol_to_a1(row_number, index + 1), "values": [[value]]}
        for row_number in matching_rows
        for index, value in zip(indexes, values)
    ]
    if changes:
        table.worksheet.batch_update(changes, value_input_option=ValueInputOption.raw)

    return len(matching_rows)
