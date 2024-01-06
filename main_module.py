import gspread
from oauth2client.service_account import ServiceAccountCredentials
from select_operations import execute_select
from insert_operations import execute_insert
from update_operations import execute_update
from delete_operations import execute_delete

class GoogleSheetDB:
    def __init__(self, spreadsheet_id, credentials_file=None):
        self.scope = ["https://www.googleapis.com/auth/spreadsheets"]
        if credentials_file:
            self.creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, self.scope)
        else:
            self.creds = ServiceAccountCredentials.get_application_default()

        self.client = gspread.authorize(self.creds)
        self.sheet = self.client.open_by_key(spreadsheet_id)

    def execute_query(self, query):
        query = query.upper()

        if query.startswith("SELECT"):
            return execute_select(query, self.sheet)
        elif query.startswith("INSERT"):
            return execute_insert(query, self.sheet)
        elif query.startswith("UPDATE"):
            return execute_update(query, self.sheet)
        elif query.startswith("DELETE"):
            return execute_delete(query, self.sheet)
        else:
            return "Unsupported operation"
