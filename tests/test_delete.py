"""DELETE must remove exactly the matching rows, however many there are."""
import pytest

from delete_operations import _contiguous_runs


def teams(*rows):
    return {"SHEET1": [["NAME", "TEAM"], *[list(r) for r in rows]]}


def test_deletes_every_matching_row_and_nothing_else(make_db):
    db, api = make_db(teams(("A", "RED"), ("B", "RED"), ("C", "BLUE"), ("D", "BLUE")))

    assert db.execute_query("DELETE FROM SHEET1 WHERE TEAM = 'RED'") == "Deletion successful"

    assert api.values("SHEET1") == [["NAME", "TEAM"], ["C", "BLUE"], ["D", "BLUE"]]


def test_deletes_scattered_matches(make_db):
    db, api = make_db(teams(("A", "RED"), ("B", "BLUE"), ("C", "RED"), ("D", "RED"), ("E", "BLUE"), ("F", "RED")))

    db.execute_query("DELETE FROM SHEET1 WHERE TEAM = 'RED'")

    assert api.values("SHEET1") == [["NAME", "TEAM"], ["B", "BLUE"], ["E", "BLUE"]]


def test_all_matches_are_deleted_in_one_request_bottom_up(make_db):
    db, api = make_db(teams(("A", "RED"), ("B", "BLUE"), ("C", "RED"), ("D", "RED")))

    db.execute_query("DELETE FROM SHEET1 WHERE TEAM = 'RED'")

    assert api.calls.count("batch_update") == 1
    ranges = [r["deleteDimension"]["range"] for r in api.batch_updates[0]["requests"]]
    assert [(r["startIndex"], r["endIndex"]) for r in ranges] == [(3, 5), (1, 2)]


def test_only_the_where_column_is_matched(make_db):
    db, api = make_db({"SHEET1": [["NAME", "NICKNAME"], ["SAM", "X"], ["X", "SAM"]]})

    db.execute_query("DELETE FROM SHEET1 WHERE NAME = 'SAM'")

    assert api.values("SHEET1") == [["NAME", "NICKNAME"], ["X", "SAM"]]


def test_header_row_is_never_deleted(make_db):
    db, api = make_db(teams(("A", "RED")))

    db.execute_query("DELETE FROM SHEET1 WHERE NAME = 'NAME'")

    assert api.values("SHEET1") == [["NAME", "TEAM"], ["A", "RED"]]
    assert api.calls.count("batch_update") == 0


def test_no_matches_sends_no_delete(make_db):
    db, api = make_db(teams(("A", "RED")))

    assert db.execute_query("DELETE FROM SHEET1 WHERE TEAM = 'GREEN'") == "Deletion successful"

    assert api.values("SHEET1") == [["NAME", "TEAM"], ["A", "RED"]]
    assert api.calls.count("batch_update") == 0


def test_unknown_column_is_an_error(make_db):
    db, api = make_db(teams(("A", "RED")))

    assert db.execute_query("DELETE FROM SHEET1 WHERE COLOUR = 'RED'") == (
        "Error executing DELETE: Column COLOUR not found"
    )
    assert len(api.values("SHEET1")) == 2


def test_can_delete_every_data_row_under_a_frozen_header(make_db):
    # A grid with no spare rows: deleting every data row would leave only the
    # frozen header, which Google Sheets refuses unless a blank row is kept.
    db, api = make_db(teams(("A", "RED"), ("B", "RED")), row_count=3, frozen_rows=1)

    assert db.execute_query("DELETE FROM SHEET1 WHERE TEAM = 'RED'") == "Deletion successful"

    assert api.values("SHEET1") == [["NAME", "TEAM"]]
    assert api.sheet("SHEET1")["row_count"] == 2


@pytest.mark.parametrize("rows, runs", [
    ([5], [(5, 5)]),
    ([8, 7, 6], [(6, 8)]),
    ([9, 7, 6, 3, 2], [(9, 9), (6, 7), (2, 3)]),
])
def test_contiguous_runs(rows, runs):
    assert _contiguous_runs(rows) == runs
