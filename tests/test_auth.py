import google.auth
import gspread
import pytest

import googlesheetsdb.database as database
from fake_sheets import FakeSheetsAPI
from googlesheetsdb import SCOPES, GoogleSheetDB


@pytest.fixture
def api():
    return FakeSheetsAPI({"Sheet1": [["Name"]]})


def test_service_account_file_is_used_with_sheets_scope(monkeypatch, api):
    seen = {}

    def fake_service_account(filename, scopes):
        seen.update(filename=filename, scopes=scopes)
        return api.gspread_client()

    monkeypatch.setattr(gspread, "service_account", fake_service_account)

    db = GoogleSheetDB(api.spreadsheet_id, "path/to/key.json")

    assert seen == {"filename": "path/to/key.json", "scopes": SCOPES}
    assert db.sheet.id == api.spreadsheet_id


def test_application_default_credentials_are_requested_with_sheets_scope(monkeypatch, api):
    credentials = object()
    seen = {}

    def fake_default(scopes):
        seen["scopes"] = scopes
        return credentials, "some-project"

    def fake_authorize(creds):
        seen["credentials"] = creds
        return api.gspread_client()

    monkeypatch.setattr(google.auth, "default", fake_default)
    monkeypatch.setattr(gspread, "authorize", fake_authorize)

    db = GoogleSheetDB(api.spreadsheet_id)

    assert seen == {"scopes": SCOPES, "credentials": credentials}
    assert db.sheet.id == api.spreadsheet_id


def test_from_oauth_runs_the_gspread_oauth_flow(monkeypatch, api):
    seen = {}

    def fake_oauth(scopes, credentials_filename, authorized_user_filename):
        seen.update(scopes=scopes, secrets=credentials_filename, token=authorized_user_filename)
        return api.gspread_client()

    monkeypatch.setattr(gspread, "oauth", fake_oauth)

    db = GoogleSheetDB.from_oauth(api.spreadsheet_id, "client_secret.json", "token.json")

    assert seen == {"scopes": SCOPES, "secrets": "client_secret.json", "token": "token.json"}
    assert db.sheet.id == api.spreadsheet_id


def test_from_oauth_defaults_to_gspread_config_files(monkeypatch, api):
    seen = {}

    def fake_oauth(scopes, credentials_filename, authorized_user_filename):
        seen.update(secrets=credentials_filename, token=authorized_user_filename)
        return api.gspread_client()

    monkeypatch.setattr(gspread, "oauth", fake_oauth)

    GoogleSheetDB.from_oauth(api.spreadsheet_id)

    assert seen == {
        "secrets": gspread.auth.DEFAULT_CREDENTIALS_FILENAME,
        "token": gspread.auth.DEFAULT_AUTHORIZED_USER_FILENAME,
    }


def test_given_client_skips_authentication(monkeypatch, api):
    def fail(*args, **kwargs):
        raise AssertionError("should not authenticate when a client is given")

    monkeypatch.setattr(gspread, "service_account", fail)
    monkeypatch.setattr(google.auth, "default", fail)

    db = GoogleSheetDB(api.spreadsheet_id, "ignored.json", client=api.gspread_client())

    assert db.client is not None
    assert db.sheet.id == api.spreadsheet_id


def test_unknown_spreadsheet_raises(api):
    with pytest.raises(gspread.SpreadsheetNotFound):
        GoogleSheetDB("no-such-spreadsheet", client=api.gspread_client())


def test_scope_is_sheets_only():
    assert database.SCOPES == ["https://www.googleapis.com/auth/spreadsheets"]
