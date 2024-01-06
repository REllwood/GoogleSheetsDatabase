import gspread


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
            cell_list = worksheet.findall(where_value)

            for cell in cell_list:
                if cell.col == worksheet.find(where_column).col:
                    worksheet.delete_row(cell.row)

            return "Deletion successful"
        else:
            return "DELETE query requires a WHERE clause"
    except Exception as e:
        return f"Error executing DELETE: {str(e)}"
