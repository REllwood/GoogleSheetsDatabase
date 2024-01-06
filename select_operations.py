import gspread

def execute_select(query, sheet):
    """
    Executes a SELECT query on the provided Google Sheet.

    Args:
    - query (str): The SQL-like SELECT query to execute.
    - sheet (gspread.Spreadsheet): The Google Sheet instance.

    Returns:
    - list: A list of dictionaries representing records retrieved from the specified sheet.
      Each dictionary corresponds to a row in the sheet where keys are column headers and
      values are cell values.

    Raises:
    - Exception: If an error occurs during the execution of the SELECT query.
    """
    try:
        parts = query.split(' ')
        sheet_name = parts[3]
        worksheet = sheet.worksheet(sheet_name)
        records = worksheet.get_all_records()
        return records
    except Exception as e:
        return f"Error executing SELECT: {str(e)}"
