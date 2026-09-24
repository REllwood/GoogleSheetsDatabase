"""
Runs every operation against a real Google Sheet, to check the library against Google
itself rather than the in-memory fake.

Skipped unless both of these environment variables are set:
- GOOGLESHEETSDB_TEST_SPREADSHEET_ID: a spreadsheet you don't mind the tests writing to
- GOOGLESHEETSDB_TEST_CREDENTIALS: path to a service account key with Editor access to it

Each test works in a new worksheet, which is deleted afterwards.
"""
import os
import uuid

import pytest

from googlesheetsdb import ColumnNotFoundError, GoogleSheetDB, QuerySyntaxError

SPREADSHEET_ID = os.environ.get("GOOGLESHEETSDB_TEST_SPREADSHEET_ID")
CREDENTIALS = os.environ.get("GOOGLESHEETSDB_TEST_CREDENTIALS")

pytestmark = pytest.mark.skipif(
    not (SPREADSHEET_ID and CREDENTIALS),
    reason="set GOOGLESHEETSDB_TEST_SPREADSHEET_ID and GOOGLESHEETSDB_TEST_CREDENTIALS "
    "to test against a real Google Sheet",
)


@pytest.fixture
def live():
    """Yields (db, worksheet, quoted table name) for a fresh worksheet with a header row."""
    db = GoogleSheetDB(SPREADSHEET_ID, CREDENTIALS)
    title = f"googlesheetsdb test {uuid.uuid4().hex[:8]}"
    worksheet = db.sheet.add_worksheet(title, rows=10, cols=5)
    try:
        worksheet.update([["Name", "Postcode", "Age", "Member", "Notes"]], "A1")
        worksheet.freeze(rows=1)
        yield db, worksheet, f'"{title}"'
    finally:
        db.sheet.del_worksheet(worksheet)


def test_round_trip(live):
    db, _, table = live

    assert db.execute_query(
        f"INSERT INTO {table} (Name, Postcode, Age, Member) VALUES "
        "('Ada', '0800', 36, TRUE), ('Bob', '3000', 52, FALSE), ('Cy', '0200', 28, TRUE)"
    ) == 3
    assert db.execute_query(f"SELECT * FROM {table} WHERE Name = ?", ["Ada"]) == [
        {"Name": "Ada", "Postcode": "0800", "Age": 36, "Member": True, "Notes": None},
    ]
    assert db.execute_query(f"UPDATE {table} SET Age = 37, Notes = ? WHERE Name = 'Ada'", ["=1+1"]) == 1
    assert db.execute_query(f"SELECT Name, Age, Notes FROM {table} WHERE Age > 30 AND Member = TRUE") == [
        {"Name": "Ada", "Age": 37, "Notes": "=1+1"},
    ]
    assert db.execute_query(f"SELECT Name FROM {table} WHERE Postcode = 800") == []
    assert db.execute_query(f"DELETE FROM {table} WHERE Member = TRUE") == 2
    assert db.execute_query(f"SELECT Name FROM {table}") == [{"Name": "Bob"}]


def test_deleting_every_row_under_a_frozen_header(live):
    db, worksheet, table = live
    db.execute_query(f"INSERT INTO {table} (Name) VALUES ('a'), ('b'), ('c')")
    worksheet.resize(rows=4)  # header plus the three rows: no spare rows left

    assert db.execute_query(f"DELETE FROM {table} WHERE Name IS NOT NULL") == 3
    assert db.execute_query(f"SELECT * FROM {table}") == []


def test_errors_are_raised(live):
    db, _, table = live

    with pytest.raises(ColumnNotFoundError):
        db.execute_query(f"SELECT Height FROM {table}")
    with pytest.raises(QuerySyntaxError):
        db.execute_query(f"SELECT * FROM {table} WHERE")
