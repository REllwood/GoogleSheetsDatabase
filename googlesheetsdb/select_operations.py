from .sheet_table import open_table


def execute_select(statement, sheet):
    """
    Executes a SELECT statement on the provided Google Sheet.

    Args:
    - statement (query_parser.Select): The parsed SELECT statement.
    - sheet (gspread.Spreadsheet): The Google Sheet instance.

    Returns:
    - list: A dictionary per matching row, keyed by column name. SELECT * gives every
      named column in sheet order; otherwise the listed columns, in the order listed.

    Raises:
    - TableNotFoundError: If no worksheet has the table's name.
    - ColumnNotFoundError: If a column isn't in the header row.
    - QueryError: If the header row repeats a column name.
    """
    table = open_table(sheet, statement.table)
    indexes = None if statement.columns is None else table.column_indexes(statement.columns)
    return [table.record(row, indexes) for _, row in table.matching_rows(statement.where)]
