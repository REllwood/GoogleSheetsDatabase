HEADER_ROW = 1


def execute_delete(query, sheet):
    """
     Executes a DELETE query on the provided Google Sheet.

     Args:
     - query (str): The SQL-like DELETE query to execute.
     - sheet (gspread.Spreadsheet): The Google Sheet instance.

     Returns:
     - str: Indicates the status of the deletion operation. Returns "Deletion successful"
       upon successful execution. If the DELETE query is missing a WHERE clause, it returns
       "DELETE query requires a WHERE clause".

     Raises:
     - Exception: If an error occurs during the execution of the DELETE query.
     """
    try:
        parts = query.split(' ')
        sheet_name = parts[2]
        where_index = query.find('WHERE')

        if where_index != -1:
            where_clause = query[where_index + len('WHERE'):].strip()
            where_parts = where_clause.split('=')
            where_column = where_parts[0].strip()
            where_value = where_parts[1].strip().strip("'")

            worksheet = sheet.worksheet(sheet_name)
            column = worksheet.find(where_column, in_row=HEADER_ROW)
            if column is None:
                raise ValueError(f"Column {where_column} not found")

            matching_rows = [
                cell.row
                for cell in worksheet.findall(where_value, in_column=column.col)
                if cell.row > HEADER_ROW
            ]
            delete_rows_bottom_up(worksheet, matching_rows)

            return "Deletion successful"
        else:
            return "DELETE query requires a WHERE clause"
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
