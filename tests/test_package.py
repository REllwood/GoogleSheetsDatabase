from pathlib import Path

import googlesheetsdb


def test_public_api():
    assert set(googlesheetsdb.__all__) == {"GoogleSheetDB", "SCOPES"}


def test_main_module_shim_still_works_from_a_checkout(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent))
    import main_module

    assert main_module.GoogleSheetDB is googlesheetsdb.GoogleSheetDB
