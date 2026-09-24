from gspread.utils import InsertDataOption, ValueInputOption

from .errors import QueryError
from .sheet_table import open_table


def execute_insert(statement, sheet):
    """
    Executes an INSERT statement on the provided Google Sheet.

    Values are matched to the listed columns by name; columns that aren't listed are left
    blank. Without a column list, values fill the named columns from left to right. All
    rows are appended below the table in a single request, and stored exactly as given:
    text stays text and numbers stay numbers.

    Args:
    - statement (query_parser.Insert): The parsed INSERT statement.
    - sheet (gspread.Spreadsheet): The Google Sheet instance.

    Returns:
    - str: "Insertion successful", or a description of the error.
    """
    try:
        table = open_table(sheet, statement.table)
        table.require_header()
        if statement.columns is None:
            indexes = table.named_columns
        else:
            indexes = table.column_indexes(statement.columns)

        new_rows = []
        for number, values in enumerate(statement.rows, start=1):
            if len(values) != len(indexes):
                raise QueryError(
                    f"Row {number} has {len(values)} value(s) for {len(indexes)} column(s)"
                )
            row = [""] * table.width
            for index, value in zip(indexes, values):
                row[index] = "" if value is None else value
            new_rows.append(row)

        table.worksheet.append_rows(
            new_rows,
            value_input_option=ValueInputOption.raw,
            insert_data_option=InsertDataOption.insert_rows,
            table_range="A1",
        )
        return "Insertion successful"
    except Exception as e:
        return f"Error executing INSERT: {str(e)}"
