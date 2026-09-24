"""Checks that the fake behaves like the Sheets API where the library depends on it."""
import pytest
from gspread.exceptions import APIError

from fake_sheets import FakeSheetsAPI


@pytest.fixture
def worksheet():
    api = FakeSheetsAPI({"My 'Tab'": [["A", "B", ""], ["x", 1, ""], ["", "", ""], ["y", 2.5, True]]})
    spreadsheet = api.gspread_client().open_by_key(api.spreadsheet_id)
    return api, spreadsheet.worksheet("My 'Tab'")


def test_responses_trim_trailing_blanks(worksheet):
    api, ws = worksheet
    assert api.values_get(api.spreadsheet_id, "'My ''Tab'''")["values"] == [
        ["A", "B"], ["x", "1"], [], ["y", "2.5", "TRUE"],
    ]


def test_unformatted_values_keep_types(worksheet):
    _, ws = worksheet
    assert ws.get_values(value_render_option="UNFORMATTED_VALUE")[3] == ["y", 2.5, True]


def test_single_cell_and_bounded_ranges(worksheet):
    api, _ = worksheet
    assert api.values_get(api.spreadsheet_id, "'My ''Tab'''!B2")["values"] == [["1"]]
    assert api.values_get(api.spreadsheet_id, "'My ''Tab'''!A2:B")["values"] == [["x", "1"], [], ["y", "2.5"]]


def test_raw_input_is_stored_literally_and_user_entered_is_parsed(worksheet):
    api, ws = worksheet
    ws.update_acell("A5", "'0800")  # update_acell uses USER_ENTERED
    ws.batch_update([{"range": "B5", "values": [["'0800"]]}], raw=True)
    assert api.values("My 'Tab'")[4] == ["0800", "'0800"]


def test_append_goes_after_the_last_row_with_data(worksheet):
    api, ws = worksheet
    ws.append_rows([["z", 3]], value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1")
    assert api.values("My 'Tab'")[4] == ["z", 3]


def test_batch_update_is_atomic(worksheet):
    api, ws = worksheet
    before = api.values("My 'Tab'")
    with pytest.raises(APIError):
        ws.spreadsheet.batch_update({"requests": [
            {"deleteDimension": {"range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": 1, "endIndex": 2}}},
            {"deleteDimension": {"range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": 5000, "endIndex": 5001}}},
        ]})
    assert api.values("My 'Tab'") == before


def test_cannot_delete_every_non_frozen_row():
    api = FakeSheetsAPI()
    api.add_sheet("S", [["H"], ["a"]], row_count=2, frozen_rows=1)
    ws = api.gspread_client().open_by_key(api.spreadsheet_id).worksheet("S")
    with pytest.raises(APIError, match="non-frozen"):
        ws.delete_rows(2)


def test_unfaked_requests_fail_loudly(worksheet):
    _, ws = worksheet
    with pytest.raises(NotImplementedError):
        ws.format("A1", {"textFormat": {"bold": True}})
