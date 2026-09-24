from .sheet_table import open_table


def execute_delete(statement, sheet):
    """
    Executes a DELETE statement on the provided Google Sheet.

    Args:
    - statement (query_parser.Delete): The parsed DELETE statement.
    - sheet (gspread.Spreadsheet): The Google Sheet instance.

    Returns:
    - str: "Deletion successful". If the DELETE query is missing a WHERE clause, it returns
      "DELETE query requires a WHERE clause". On failure, a description of the error.
    """
    try:
        if statement.where is None:
            return "DELETE query requires a WHERE clause"

        table = open_table(sheet, statement.table)
        matching_rows = [row_number for row_number, _ in table.matching_rows(statement.where)]
        delete_rows_bottom_up(table.worksheet, matching_rows)

        return "Deletion successful"
    except Exception as e:
        return f"Error executing DELETE: {str(e)}"


def delete_rows_bottom_up(worksheet, row_numbers):
    """
    Deletes rows from a worksheet in a single, atomic request.

    Rows are removed from the bottom up, so deleting one row never shifts another row
    that is still waiting to be deleted. Neighbouring rows are removed together.

    Args:
    - worksheet (gspread.Worksheet): The worksheet to delete rows from.
    - row_numbers (iterable of int): 1-based numbers of the rows to delete.
    """
    rows = sorted(set(row_numbers), reverse=True)
    if not rows:
        return

    requests = []
    # Google Sheets refuses to delete every non-frozen row of a sheet, so add a blank
    # row at the bottom first when a delete would otherwise leave none.
    if worksheet.row_count - len(rows) <= worksheet.frozen_row_count:
        requests.append({"appendDimension": {"sheetId": worksheet.id, "dimension": "ROWS", "length": 1}})

    for first, last in _contiguous_runs(rows):
        requests.append({
            "deleteDimension": {
                "range": {
                    "sheetId": worksheet.id,
                    "dimension": "ROWS",
                    "startIndex": first - 1,
                    "endIndex": last,
                }
            }
        })

    worksheet.spreadsheet.batch_update({"requests": requests})


def _contiguous_runs(rows_descending):
    """Groups descending row numbers into (first, last) runs, bottom run first."""
    runs = []
    for row in rows_descending:
        if runs and runs[-1][0] == row + 1:
            runs[-1][0] = row
        else:
            runs.append([row, row])
    return [tuple(run) for run in runs]
