"""An in-memory stand-in for the Google Sheets REST API, for tests.

FakeSheetsAPI subclasses gspread's HTTPClient, so the real gspread Client,
Spreadsheet and Worksheet code runs unchanged on top of it; only the HTTP calls
are replaced. It models the parts of the API this library relies on:

- A1 ranges such as 'Sheet1', 'Sheet1'!A1 and 'Sheet1'!B2:C5
- RAW and USER_ENTERED input, and FORMATTED_VALUE / UNFORMATTED_VALUE output
- responses that trim trailing blank rows and cells, as the real API does
- values:append, values:batchUpdate, and spreadsheets:batchUpdate with
  deleteDimension / appendDimension requests, applied atomically
- the API's refusal to delete every row (or every non-frozen row) of a sheet

Anything else raises NotImplementedError, so a test fails loudly rather than
passing against behaviour the fake doesn't model.
"""
import copy
import json
import re

import gspread
import requests
from gspread.exceptions import APIError
from gspread.http_client import HTTPClient

_RANGE = re.compile(
    r"^(?:'(?P<quoted>(?:[^']|'')*)'|(?P<plain>[^'!]+))"
    r"(?:!(?P<c1>[A-Z]*)(?P<r1>\d*)(?::(?P<c2>[A-Z]*)(?P<r2>\d*))?)?$"
)
_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def api_error(code, message, status="INVALID_ARGUMENT"):
    """Builds the gspread APIError that a real HTTP error response would produce."""
    response = requests.Response()
    response.status_code = code
    response._content = json.dumps(
        {"error": {"code": code, "message": message, "status": status}}
    ).encode()
    return APIError(response)


def _col_number(letters):
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - ord("A") + 1
    return number


def _normalise_number(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _raw(value):
    return "" if value is None else value


def _user_entered(value):
    """Rough model of how Sheets parses text typed into a cell."""
    if not isinstance(value, str):
        return _raw(value)
    if value.startswith("'"):
        return value[1:]
    if value.upper() in ("TRUE", "FALSE"):
        return value.upper() == "TRUE"
    if _NUMBER.match(value.strip()):
        return _normalise_number(float(value))
    return value


def _formatted(value):
    """Rough model of Sheets' default ('Automatic') number formatting."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(_normalise_number(value))
    return value


class FakeSheetsAPI(HTTPClient):
    def __init__(self, tabs=None, spreadsheet_id="test-spreadsheet-id", title="Test spreadsheet"):
        """
        Args:
        - tabs (dict): Maps each worksheet title to its rows, e.g.
          {"Sheet1": [["Name", "Age"], ["Frodo", 50]]}. Values are stored as given
          (str, int, float or bool); "" or None is a blank cell.
        """
        # HTTPClient.__init__ is deliberately skipped: no credentials, no network.
        self.timeout = None
        self.spreadsheet_id = spreadsheet_id
        self.title = title
        self.sheets = []
        self.calls = []
        self.batch_updates = []
        self.values_get_params = []
        for sheet_title, rows in (tabs or {}).items():
            self.add_sheet(sheet_title, rows)

    # -- test helpers ---------------------------------------------------------

    def add_sheet(self, title, rows=(), row_count=1000, column_count=26, frozen_rows=0):
        rows = [[_raw(v) for v in row] for row in rows]
        self.sheets.append({
            "sheetId": 1000 + len(self.sheets),
            "title": title,
            "rows": rows,
            "row_count": max(row_count, len(rows)),
            "column_count": max([column_count] + [len(r) for r in rows]),
            "frozen_rows": frozen_rows,
        })

    def gspread_client(self):
        """Returns a real gspread.Client whose HTTP layer is this fake."""
        return gspread.Client(None, http_client=lambda auth, session: self)

    def values(self, title):
        """Stored cell values of a worksheet, trimmed like an API response."""
        return self._trimmed(self._sheet_by_title(title)["rows"])

    def sheet(self, title):
        return self._sheet_by_title(title)

    # -- faked HTTPClient methods ---------------------------------------------

    def request(self, *args, **kwargs):
        raise NotImplementedError(f"FakeSheetsAPI does not fake this request: {args!r}")

    def fetch_sheet_metadata(self, id, params=None):
        self.calls.append("fetch_sheet_metadata")
        self._check_id(id)
        return {
            "spreadsheetId": id,
            "properties": {"title": self.title},
            "sheets": [{"properties": self._sheet_properties(s, i)} for i, s in enumerate(self.sheets)],
        }

    def spreadsheets_get(self, id, params=None):
        return self.fetch_sheet_metadata(id, params)

    def values_get(self, id, range, params=None):
        self.calls.append("values_get")
        self.values_get_params.append(dict(params or {}))
        self._check_id(id)
        sheet, (r1, c1, r2, c2) = self._parse_range(range)
        render = (params or {}).get("valueRenderOption") or "FORMATTED_VALUE"
        if render == "FORMATTED_VALUE":
            render_cell = _formatted
        elif render == "UNFORMATTED_VALUE":
            render_cell = _normalise_number
        else:
            raise NotImplementedError(f"valueRenderOption {render}")

        rows = sheet["rows"][r1 - 1:r2]
        values = [[render_cell(v) for v in row[c1 - 1:c2]] for row in rows]
        response = {"range": range, "majorDimension": "ROWS"}
        values = self._trimmed(values)
        if values:
            response["values"] = values
        return response

    def values_update(self, id, range, params=None, body=None):
        self.calls.append("values_update")
        self._check_id(id)
        self._write(range, body["values"], (params or {}).get("valueInputOption"))
        return {"spreadsheetId": id, "updatedRange": range}

    def values_batch_update(self, id, body=None):
        self.calls.append("values_batch_update")
        self._check_id(id)
        option = body.get("valueInputOption")
        with self._atomic():
            for value_range in body["data"]:
                self._write(value_range["range"], value_range["values"], option)
        return {"spreadsheetId": id, "totalUpdatedCells": sum(len(r) for d in body["data"] for r in d["values"])}

    def values_append(self, id, range, params, body):
        self.calls.append("values_append")
        self._check_id(id)
        sheet, _ = self._parse_range(range)
        option = self._value_input_option(params.get("valueInputOption"))
        new_rows = [[option(v) for v in row] for row in body["values"]]

        # The table ends at the last row holding any data.
        end = len(self._trimmed(sheet["rows"]))
        if params.get("insertDataOption") == "INSERT_ROWS":
            sheet["rows"][end:end] = new_rows
            sheet["row_count"] += len(new_rows)
        else:
            del sheet["rows"][end:end + len(new_rows)]
            sheet["rows"][end:end] = new_rows
            sheet["row_count"] = max(sheet["row_count"], end + len(new_rows))
        sheet["column_count"] = max([sheet["column_count"]] + [len(r) for r in new_rows])
        return {
            "spreadsheetId": id,
            "updates": {"updatedRows": len(new_rows), "updatedRange": f"'{sheet['title']}'!A{end + 1}"},
        }

    def batch_update(self, id, body):
        self.calls.append("batch_update")
        self.batch_updates.append(copy.deepcopy(body))
        self._check_id(id)
        with self._atomic():
            for request in body["requests"]:
                (kind, args), = request.items()
                if kind == "deleteDimension":
                    self._delete_dimension(args["range"])
                elif kind == "appendDimension":
                    self._append_dimension(args)
                else:
                    raise NotImplementedError(f"batchUpdate request {kind}")
        return {"spreadsheetId": id, "replies": [{} for _ in body["requests"]]}

    # -- internals ------------------------------------------------------------

    def _check_id(self, id):
        if id != self.spreadsheet_id:
            raise api_error(404, "Requested entity was not found.", "NOT_FOUND")

    def _sheet_properties(self, sheet, index):
        grid = {"rowCount": sheet["row_count"], "columnCount": sheet["column_count"]}
        if sheet["frozen_rows"]:
            grid["frozenRowCount"] = sheet["frozen_rows"]
        return {
            "sheetId": sheet["sheetId"],
            "title": sheet["title"],
            "index": index,
            "sheetType": "GRID",
            "gridProperties": grid,
        }

    def _sheet_by_title(self, title):
        for sheet in self.sheets:
            if sheet["title"] == title:
                return sheet
        raise api_error(400, f"Unable to parse range: {title}")

    def _sheet_by_id(self, sheet_id):
        for sheet in self.sheets:
            if sheet["sheetId"] == sheet_id:
                return sheet
        raise api_error(400, f"No grid with id: {sheet_id}")

    def _parse_range(self, range):
        """Returns (sheet, (first_row, first_col, last_row, last_col)), 1-based and inclusive."""
        match = _RANGE.match(range)
        if not match:
            raise NotImplementedError(f"range {range!r}")
        title = match["quoted"].replace("''", "'") if match["quoted"] is not None else match["plain"]
        sheet = self._sheet_by_title(title)
        r1 = int(match["r1"]) if match["r1"] else 1
        c1 = _col_number(match["c1"]) if match["c1"] else 1
        if match["c2"] is None and match["r2"] is None:
            single_cell = bool(match["r1"] and match["c1"])
            r2 = r1 if single_cell else sheet["row_count"]
            c2 = c1 if single_cell else sheet["column_count"]
        else:
            r2 = int(match["r2"]) if match["r2"] else sheet["row_count"]
            c2 = _col_number(match["c2"]) if match["c2"] else sheet["column_count"]
        return sheet, (r1, c1, r2, c2)

    @staticmethod
    def _value_input_option(option):
        if option == "RAW":
            return _raw
        if option == "USER_ENTERED":
            return _user_entered
        raise api_error(400, f"Invalid valueInputOption: {option}")

    def _write(self, range, values, option):
        sheet, (r1, c1, _, _) = self._parse_range(range)
        convert = self._value_input_option(option)
        for i, row in enumerate(values):
            for j, value in enumerate(row):
                self._set_cell(sheet, r1 + i, c1 + j, convert(value))

    @staticmethod
    def _set_cell(sheet, row, col, value):
        if row > sheet["row_count"]:
            raise api_error(400, f"Range exceeds grid limits. Max rows: {sheet['row_count']}")
        rows = sheet["rows"]
        while len(rows) < row:
            rows.append([])
        cells = rows[row - 1]
        while len(cells) < col:
            cells.append("")
        cells[col - 1] = value
        sheet["column_count"] = max(sheet["column_count"], col)

    def _delete_dimension(self, grid_range):
        if grid_range.get("dimension") != "ROWS":
            raise NotImplementedError("deleteDimension on columns")
        sheet = self._sheet_by_id(grid_range["sheetId"])
        start, end = grid_range["startIndex"], grid_range["endIndex"]
        if not 0 <= start < end <= sheet["row_count"]:
            raise api_error(400, "Invalid requests[0].deleteDimension: Index out of bounds.")
        remaining = sheet["row_count"] - (end - start)
        if remaining == 0:
            raise api_error(400, "Invalid requests[0].deleteDimension: You can't delete all the rows on the sheet.")
        if remaining <= sheet["frozen_rows"]:
            raise api_error(400, "Invalid requests[0].deleteDimension: You can't delete all non-frozen rows.")
        del sheet["rows"][start:end]
        sheet["row_count"] = remaining

    def _append_dimension(self, args):
        if args.get("dimension") != "ROWS":
            raise NotImplementedError("appendDimension on columns")
        self._sheet_by_id(args["sheetId"])["row_count"] += args["length"]

    @staticmethod
    def _trimmed(rows):
        trimmed = []
        for row in rows:
            row = list(row)
            while row and row[-1] == "":
                row.pop()
            trimmed.append(row)
        while trimmed and not trimmed[-1]:
            trimmed.pop()
        return trimmed

    def _atomic(self):
        return _Atomic(self)


class _Atomic:
    """Restores the fake's sheets if a batch fails part-way, as the real API does."""

    def __init__(self, api):
        self.api = api

    def __enter__(self):
        self.saved = copy.deepcopy(self.api.sheets)

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.api.sheets = self.saved
        return False
