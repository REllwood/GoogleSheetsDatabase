from gspread.utils import ValueInputOption, rowcol_to_a1

from .sheet_table import open_table


def execute_update(statement, sheet):
    """
    Executes an UPDATE statement on the provided Google Sheet.

    The sheet is read once, and every changed cell is written in a single request.

    Args:
    - statement (query_parser.Update): The parsed UPDATE statement.
    - sheet (gspread.Spreadsheet): The Google Sheet instance.

    Returns:
    - str: "Update successful". If the UPDATE query is missing a WHERE clause, it returns
      "UPDATE query requires a WHERE clause". On failure, a description of the error.
    """
    try:
        if statement.where is None:
            return "UPDATE query requires a WHERE clause"

        table = open_table(sheet, statement.table)
        indexes = table.column_indexes([column for column, _ in statement.assignments])
        values = ["" if value is None else value for _, value in statement.assignments]

        changes = [
            {"range": rowcol_to_a1(row_number, index + 1), "values": [[value]]}
            for row_number, _ in table.matching_rows(statement.where)
            for index, value in zip(indexes, values)
        ]
        if changes:
            table.worksheet.batch_update(changes, value_input_option=ValueInputOption.raw)

        return "Update successful"
    except Exception as e:
        return f"Error executing UPDATE: {str(e)}"
