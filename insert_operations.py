import gspread


def execute_insert(query, sheet):
    """
    Executes an INSERT query on the provided Google Sheet.

    Args:
    - query (str): The SQL-like INSERT query to execute.
    - sheet (gspread.Spreadsheet): The Google Sheet instance.

    Returns:
    - str: Indicates the status of the insertion operation. Returns "Insertion successful"
      upon successful execution.

    Raises:
    - Exception: If an error occurs during the execution of the INSERT query.
    """
    try:
        parts = query.split(' ')
        sheet_name = parts[2]
        values_start_index = query.find('VALUES') + len('VALUES')

        values = query[values_start_index + 1:].replace("(", "").replace(")", "").split(',')

        worksheet = sheet.worksheet(sheet_name)
        worksheet.append_row(values)

        return "Insertion successful"
    except Exception as e:
        return f"Error executing INSERT: {str(e)}"
