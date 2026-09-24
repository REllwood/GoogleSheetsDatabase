"""Each operation, end to end against the real gspread 6 client.

execute_query upper-cases the whole query, so these fixtures use upper-case
tab names, headers and values.
"""

HOBBITS = {"SHEET1": [["NAME", "AGE"], ["FRODO", 50], ["SAM", 38], ["PIPPIN", 28]]}


def test_select_returns_every_record(make_db):
    db, _ = make_db(HOBBITS)

    assert db.execute_query("SELECT * FROM SHEET1") == [
        {"NAME": "FRODO", "AGE": 50},
        {"NAME": "SAM", "AGE": 38},
        {"NAME": "PIPPIN", "AGE": 28},
    ]


def test_insert_appends_a_row(make_db):
    db, api = make_db(HOBBITS)

    assert db.execute_query("INSERT INTO SHEET1 (NAME, AGE) VALUES (MERRY,36)") == "Insertion successful"

    assert api.values("SHEET1")[-1] == ["MERRY", "36"]
    assert len(api.values("SHEET1")) == 5


def test_update_changes_the_matching_cell(make_db):
    db, api = make_db(HOBBITS)

    assert db.execute_query("UPDATE SHEET1 SET AGE = 51 WHERE NAME = 'FRODO'") == "Update successful"

    assert api.values("SHEET1")[1] == ["FRODO", 51]


def test_delete_removes_the_matching_row(make_db):
    db, api = make_db(HOBBITS)

    assert db.execute_query("DELETE FROM SHEET1 WHERE NAME = 'SAM'") == "Deletion successful"

    assert api.values("SHEET1") == [["NAME", "AGE"], ["FRODO", 50], ["PIPPIN", 28]]


def test_delete_without_where_is_refused(make_db):
    db, api = make_db(HOBBITS)

    assert db.execute_query("DELETE FROM SHEET1") == "DELETE query requires a WHERE clause"
    assert len(api.values("SHEET1")) == 4


def test_unsupported_statement(make_db):
    db, _ = make_db(HOBBITS)

    assert db.execute_query("DROP TABLE SHEET1") == "Unsupported operation"
