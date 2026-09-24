import google.auth
import gspread
from gspread.auth import DEFAULT_AUTHORIZED_USER_FILENAME, DEFAULT_CREDENTIALS_FILENAME
from .select_operations import execute_select
from .insert_operations import execute_insert
from .update_operations import execute_update
from .delete_operations import execute_delete

# Read/write access to Google Sheets only; the library never touches Google Drive.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetDB:
    def __init__(self, spreadsheet_id, credentials_file=None, client=None):
        """
        Opens a Google Sheet so it can be queried like a database.

        Args:
        - spreadsheet_id (str): The ID in the sheet's URL:
          https://docs.google.com/spreadsheets/d/<spreadsheet_id>/edit
        - credentials_file (str, optional): Path to a service account JSON key file.
          When omitted, Application Default Credentials are used.
        - client (gspread.Client, optional): An already authorised gspread client.
          When given, credentials_file is ignored.
        """
        if client is None:
            if credentials_file:
                client = gspread.service_account(filename=credentials_file, scopes=SCOPES)
            else:
                credentials, _ = google.auth.default(scopes=SCOPES)
                client = gspread.authorize(credentials)

        self.client = client
        self.sheet = self.client.open_by_key(spreadsheet_id)

    @classmethod
    def from_oauth(
        cls,
        spreadsheet_id,
        client_secrets_file=DEFAULT_CREDENTIALS_FILENAME,
        authorized_user_file=DEFAULT_AUTHORIZED_USER_FILENAME,
    ):
        """
        Opens a Google Sheet as a Google user, using an OAuth client ID.

        The first call opens a browser window to sign in and grant access. The resulting
        token is saved to authorized_user_file and reused on later calls.

        Args:
        - spreadsheet_id (str): The ID in the sheet's URL.
        - client_secrets_file (str, optional): Path to the OAuth client ID JSON file
          downloaded from the Google Cloud Console. Defaults to gspread's
          ~/.config/gspread/credentials.json.
        - authorized_user_file (str, optional): Where to cache the signed-in user's token.
          Defaults to gspread's ~/.config/gspread/authorized_user.json.

        Returns:
        - GoogleSheetDB: A connected instance.
        """
        client = gspread.oauth(
            scopes=SCOPES,
            credentials_filename=client_secrets_file,
            authorized_user_filename=authorized_user_file,
        )
        return cls(spreadsheet_id, client=client)

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
