import pytest

from fake_sheets import FakeSheetsAPI
from main_module import GoogleSheetDB


@pytest.fixture
def make_db():
    """Returns a factory: make_db(tabs) -> (GoogleSheetDB, FakeSheetsAPI)."""

    def _make(tabs, **sheet_options):
        api = FakeSheetsAPI()
        for title, rows in tabs.items():
            api.add_sheet(title, rows, **sheet_options)
        db = GoogleSheetDB(api.spreadsheet_id, client=api.gspread_client())
        api.calls.clear()
        return db, api

    return _make
