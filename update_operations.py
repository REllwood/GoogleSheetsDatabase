import gspread


def execute_update(query, sheet):
    """
    Executes an UPDATE query on the provided Google Sheet.

    Args:
    - query (str): The SQL-like UPDATE query to execute.
    - sheet (gspread.Spreadsheet): The Google Sheet instance.

    Returns:
    - str: Indicates the status of the update operation. Returns "Update successful"
      upon successful execution.

    Raises:
    - Exception: If an error occurs during the execution of the UPDATE query.
    """
    try:
        parts = query.split(' ')
        sheet_name = parts[1]
        set_index = query.find('SET')
        where_index = query.find('WHERE')

        set_clause = query[set_index + len('SET'): where_index].strip()
        where_clause = query[where_index + len('WHERE'):].strip()

        set_parts = set_clause.split('=')
        set_column = set_parts[0].strip()
        set_value = set_parts[1].strip().strip("'")

        where_parts = where_clause.split('=')
        where_column = where_parts[0].strip()
        where_value = where_parts[1].strip().strip("'")

        worksheet = sheet.worksheet(sheet_name)
        cell_list = worksheet.findall(where_value)

        for cell in cell_list:
            if cell.col == worksheet.find(where_column).col:
                worksheet.update_cell(cell.row, worksheet.find(set_column).col, set_value)

        return "Update successful"
    except Exception as e:
        return f"Error executing UPDATE: {str(e)}"
