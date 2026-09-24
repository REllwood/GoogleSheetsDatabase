from pathlib import Path

import pytest

import googlesheetsdb
from googlesheetsdb import ColumnNotFoundError, QueryError, QuerySyntaxError, TableNotFoundError


def test_public_api():
    assert set(googlesheetsdb.__all__) == {
        "GoogleSheetDB", "SCOPES",
        "QueryError", "QuerySyntaxError", "TableNotFoundError", "ColumnNotFoundError",
    }


@pytest.mark.parametrize("error", [QuerySyntaxError, TableNotFoundError, ColumnNotFoundError])
def test_every_query_error_can_be_caught_as_query_error(error):
    assert issubclass(error, QueryError)


def test_main_module_shim_still_works_from_a_checkout(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent))
    import main_module

    assert main_module.GoogleSheetDB is googlesheetsdb.GoogleSheetDB
    assert main_module.QueryError is googlesheetsdb.QueryError
