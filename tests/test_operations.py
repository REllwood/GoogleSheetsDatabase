"""Each operation, end to end against the real gspread 6 client and the fake Sheets API."""
import pytest

from googlesheetsdb import ColumnNotFoundError, QueryError, QuerySyntaxError, TableNotFoundError


def hobbits():
    return {"Sheet1": [
        ["Name", "Age", "Home"],
        ["Frodo", 50, "Bag End"],
        ["Sam", 38, "Bagshot Row"],
        ["Pippin", 28, "Tuckborough"],
        ["Merry", 36, ""],
    ]}


# -- the README examples --------------------------------------------------------

def test_readme_examples_work_as_written(make_db):
    db, api = make_db(hobbits())

    assert len(db.execute_query("SELECT * FROM Sheet1")) == 4
    assert db.execute_query("INSERT INTO Sheet1 (Name, Age) VALUES ('Bilbo', 111)") == 1
    assert db.execute_query("UPDATE Sheet1 SET Age = 51 WHERE Name = 'Frodo'") == 1
    assert db.execute_query("DELETE FROM Sheet1 WHERE Name = 'Pippin'") == 1

    assert api.values("Sheet1") == [
        ["Name", "Age", "Home"],
        ["Frodo", 51, "Bag End"],
        ["Sam", 38, "Bagshot Row"],
        ["Merry", 36],
        ["Bilbo", 111],
    ]


# -- SELECT ---------------------------------------------------------------------

def test_select_star_returns_every_named_column(make_db):
    db, _ = make_db(hobbits())

    assert db.execute_query("SELECT * FROM Sheet1")[0] == {"Name": "Frodo", "Age": 50, "Home": "Bag End"}


def test_select_listed_columns_in_the_order_listed(make_db):
    db, _ = make_db(hobbits())

    assert db.execute_query("SELECT Home, Name FROM Sheet1 WHERE Age < 30") == [
        {"Home": "Tuckborough", "Name": "Pippin"},
    ]


@pytest.mark.parametrize("where, names", [
    ("Age = 38", ["Sam"]),
    ("Age != 38", ["Frodo", "Pippin", "Merry"]),
    ("Age <> 38", ["Frodo", "Pippin", "Merry"]),
    ("Age > 36", ["Frodo", "Sam"]),
    ("Age >= 36", ["Frodo", "Sam", "Merry"]),
    ("Age < 36", ["Pippin"]),
    ("Age <= 36", ["Pippin", "Merry"]),
    ("Name = 'Sam'", ["Sam"]),
    ("Name = 'sam'", []),
    ("Name < 'N'", ["Frodo", "Merry"]),
    ("Age > 30 AND Age < 40", ["Sam", "Merry"]),
    ("Name = 'Frodo' OR Name = 'Merry'", ["Frodo", "Merry"]),
    ("NOT (Age > 30 AND Age < 40)", ["Frodo", "Pippin"]),
    ("Name = 'Frodo' OR Age < 30 AND Home = 'Tuckborough'", ["Frodo", "Pippin"]),
    ("Home IS NULL", ["Merry"]),
    ("Home IS NOT NULL", ["Frodo", "Sam", "Pippin"]),
    ("Home = NULL", ["Merry"]),
    ("Home != 'Bag End'", ["Sam", "Pippin", "Merry"]),
    ("Home > 'A'", ["Frodo", "Sam", "Pippin"]),
    ("Age = '38'", ["Sam"]),
])
def test_where_conditions(make_db, where, names):
    db, _ = make_db(hobbits())

    rows = db.execute_query(f"SELECT Name FROM Sheet1 WHERE {where}")

    assert [row["Name"] for row in rows] == names


def test_tolerates_spacing_semicolons_and_keyword_case(make_db):
    db, _ = make_db(hobbits())

    rows = db.execute_query("select  Name\n  from Sheet1\n  where Age = 38 ;")

    assert rows == [{"Name": "Sam"}]


def test_table_and_column_names_match_case_insensitively(make_db):
    db, _ = make_db(hobbits())

    assert db.execute_query("SELECT NAME FROM sheet1 WHERE age = 38") == [{"Name": "Sam"}]


def test_names_with_spaces_can_be_quoted(make_db):
    db, _ = make_db({"Team List": [["First Name", "Team"], ["Rosie", "Red"]]})

    assert db.execute_query('SELECT "First Name" FROM "Team List" WHERE Team = \'Red\'') == [
        {"First Name": "Rosie"},
    ]


def test_completely_empty_rows_are_skipped(make_db):
    db, _ = make_db({"Sheet1": [["Name"], ["Frodo"], [""], ["Sam"]]})

    assert db.execute_query("SELECT * FROM Sheet1") == [{"Name": "Frodo"}, {"Name": "Sam"}]


def test_select_reads_the_sheet_once(make_db):
    db, api = make_db(hobbits())

    db.execute_query("SELECT * FROM Sheet1 WHERE Age > 1")

    assert api.calls == ["fetch_sheet_metadata", "values_get"]


def test_unknown_table_and_column(make_db):
    db, _ = make_db(hobbits())

    with pytest.raises(TableNotFoundError, match="No worksheet is named 'Sheet2'. Worksheets: 'Sheet1'"):
        db.execute_query("SELECT * FROM Sheet2")
    with pytest.raises(ColumnNotFoundError, match="'Sheet1' has no column 'Height'. Columns: 'Name', 'Age', 'Home'"):
        db.execute_query("SELECT Height FROM Sheet1")


def test_duplicate_header_names_are_reported(make_db):
    db, _ = make_db({"Sheet1": [["Name", "Name"], ["a", "b"]]})

    with pytest.raises(QueryError, match=r"repeats the column name\(s\) 'Name'"):
        db.execute_query("SELECT * FROM Sheet1")


# -- INSERT ---------------------------------------------------------------------

def test_insert_stores_values_exactly_and_can_be_found_again(make_db):
    db, api = make_db(hobbits())

    db.execute_query("INSERT INTO Sheet1 (Name, Age, Home) VALUES ('Fredegar ''Fatty'' Bolger', 33, 'Crickhollow')")

    assert api.values("Sheet1")[-1] == ["Fredegar 'Fatty' Bolger", 33, "Crickhollow"]
    assert db.execute_query("SELECT Age FROM Sheet1 WHERE Name = 'Fredegar ''Fatty'' Bolger'") == [{"Age": 33}]


def test_insert_matches_values_to_columns_by_name(make_db):
    db, api = make_db(hobbits())

    db.execute_query("INSERT INTO Sheet1 (Home, Name) VALUES ('Bree', 'Butterbur')")

    assert api.values("Sheet1")[-1] == ["Butterbur", "", "Bree"]


def test_insert_without_columns_fills_them_in_order(make_db):
    db, api = make_db(hobbits())

    db.execute_query("INSERT INTO Sheet1 VALUES ('Bilbo', 111, 'Rivendell')")

    assert api.values("Sheet1")[-1] == ["Bilbo", 111, "Rivendell"]


def test_insert_several_rows_in_one_request(make_db):
    db, api = make_db(hobbits())

    db.execute_query("INSERT INTO Sheet1 (Name, Age) VALUES ('Lobelia', 90), ('Lotho', 50)")

    assert api.values("Sheet1")[-2:] == [["Lobelia", 90], ["Lotho", 50]]
    assert api.calls == ["fetch_sheet_metadata", "values_get", "values_append"]


def test_insert_value_count_must_match(make_db):
    db, api = make_db(hobbits())

    with pytest.raises(QueryError, match=r"Row 1 has 1 value\(s\) for 2 column\(s\)"):
        db.execute_query("INSERT INTO Sheet1 (Name, Age) VALUES ('Bilbo')")
    with pytest.raises(QueryError, match=r"Row 2 has 2 value\(s\) for 3 column\(s\)"):
        db.execute_query("INSERT INTO Sheet1 VALUES ('Bilbo', 111, 'Bag End'), ('Bilbo', 111)")
    assert len(api.values("Sheet1")) == 5


def test_insert_rejects_a_column_named_twice(make_db):
    db, _ = make_db(hobbits())

    with pytest.raises(QueryError, match="Column 'Name' is listed more than once"):
        db.execute_query("INSERT INTO Sheet1 (Name, name) VALUES ('a', 'b')")


def test_insert_into_a_sheet_without_a_header(make_db):
    db, _ = make_db({"Empty": []})

    with pytest.raises(ColumnNotFoundError, match="'Empty' has no header row"):
        db.execute_query("INSERT INTO Empty VALUES ('x')")


def test_formulas_are_stored_as_text_not_run(make_db):
    db, api = make_db(hobbits())

    db.execute_query("INSERT INTO Sheet1 (Name) VALUES ('=IMPORTXML(\"http://example.com\", \"//a\")')")

    assert api.values("Sheet1")[-1] == ['=IMPORTXML("http://example.com", "//a")']


# -- UPDATE ---------------------------------------------------------------------

def test_update_sets_several_columns(make_db):
    db, api = make_db(hobbits())

    db.execute_query("UPDATE Sheet1 SET Age = 51, Home = 'Rivendell' WHERE Name = 'Frodo'")

    assert api.values("Sheet1")[1] == ["Frodo", 51, "Rivendell"]


def test_update_every_match_with_one_read_and_one_write(make_db):
    db, api = make_db(hobbits())

    db.execute_query("UPDATE Sheet1 SET Home = 'The Shire' WHERE Age < 40")

    assert [row[2] for row in api.values("Sheet1")[1:]] == ["Bag End", "The Shire", "The Shire", "The Shire"]
    assert api.calls == ["fetch_sheet_metadata", "values_get", "values_batch_update"]


def test_update_to_null_clears_the_cell(make_db):
    db, api = make_db(hobbits())

    db.execute_query("UPDATE Sheet1 SET Home = NULL WHERE Name = 'Sam'")

    assert api.values("Sheet1")[2] == ["Sam", 38]


def test_update_where_value_equal_to_a_header_never_touches_the_header(make_db):
    db, api = make_db(hobbits())

    db.execute_query("UPDATE Sheet1 SET Age = 0 WHERE Name = 'Name'")

    assert api.values("Sheet1") == hobbits()["Sheet1"][:4] + [["Merry", 36]]


def test_update_without_where_is_refused(make_db):
    db, api = make_db(hobbits())

    with pytest.raises(QueryError, match="UPDATE needs a WHERE clause"):
        db.execute_query("UPDATE Sheet1 SET Age = 1")
    assert api.calls == []


def test_update_with_no_matches_writes_nothing(make_db):
    db, api = make_db(hobbits())

    db.execute_query("UPDATE Sheet1 SET Age = 1 WHERE Name = 'Gandalf'")

    assert "values_batch_update" not in api.calls


# -- DELETE ---------------------------------------------------------------------

def test_delete_value_containing_an_equals_sign_matches_exactly(make_db):
    db, api = make_db({"Sheet1": [["Key", "Value"], ["x", "a"], ["y", "a=b"], ["z", "a"]]})

    db.execute_query("DELETE FROM Sheet1 WHERE Value = 'a=b'")

    assert api.values("Sheet1") == [["Key", "Value"], ["x", "a"], ["z", "a"]]


def test_delete_with_a_compound_condition(make_db):
    db, api = make_db(hobbits())

    db.execute_query("DELETE FROM Sheet1 WHERE Age < 30 OR Home IS NULL")

    assert [row[0] for row in api.values("Sheet1")] == ["Name", "Frodo", "Sam"]


def test_delete_without_where_is_refused(make_db):
    db, api = make_db(hobbits())

    with pytest.raises(QueryError, match="DELETE needs a WHERE clause"):
        db.execute_query("DELETE FROM Sheet1")
    assert api.calls == []


# -- parameters -----------------------------------------------------------------

def test_parameters_are_stored_as_values(make_db):
    db, api = make_db(hobbits())

    db.execute_query("INSERT INTO Sheet1 (Name, Age, Home) VALUES (?, ?, ?)", ("Farmer Maggot", 70, None))

    assert api.values("Sheet1")[-1] == ["Farmer Maggot", 70]


def test_parameters_cannot_inject_query_text(make_db):
    db, api = make_db(hobbits())

    db.execute_query("DELETE FROM Sheet1 WHERE Name = ?", ["x' OR Name != 'x"])

    assert len(api.values("Sheet1")) == 5


# -- errors ---------------------------------------------------------------------

def test_syntax_errors_are_reported_before_any_api_call(make_db):
    db, api = make_db(hobbits())

    with pytest.raises(QuerySyntaxError, match="Expected SELECT, INSERT, UPDATE or DELETE, but found 'DROP'"):
        db.execute_query("DROP TABLE Sheet1")
    with pytest.raises(QuerySyntaxError, match="Expected a column name, but found the end of the query"):
        db.execute_query("  SELECT * FROM Sheet1 WHERE Age > 30 AND")
    assert api.calls == []


# -- comparison edge cases --------------------------------------------------------

@pytest.mark.parametrize("where, names", [
    ("Home != NULL", ["Frodo", "Sam", "Pippin"]),
    ("Home > NULL", []),
    ("Home > 5", []),
    ("Home != 5", ["Frodo", "Sam", "Pippin", "Merry"]),
])
def test_null_and_mismatched_types(make_db, where, names):
    db, _ = make_db(hobbits())

    assert [row["Name"] for row in db.execute_query(f"SELECT Name FROM Sheet1 WHERE {where}")] == names


@pytest.mark.parametrize("where, names", [
    ("Ringbearer = TRUE", ["Frodo"]),
    ("Ringbearer != TRUE", ["Sam", "Pippin"]),
    ("Ringbearer = FALSE", ["Sam"]),
])
def test_boolean_cells(make_db, where, names):
    db, _ = make_db({"Sheet1": [["Name", "Ringbearer"], ["Frodo", True], ["Sam", False], ["Pippin", "maybe"]]})

    assert [row["Name"] for row in db.execute_query(f"SELECT Name FROM Sheet1 WHERE {where}")] == names


def test_ambiguous_names_must_be_written_exactly(make_db):
    db, _ = make_db({"Data": [["name", "NAME"], ["a", "b"]], "DATA": [["x"]]})

    with pytest.raises(TableNotFoundError, match="More than one worksheet matches 'data'; use its exact name"):
        db.execute_query("SELECT * FROM data")
    with pytest.raises(ColumnNotFoundError, match="More than one column of 'Data' matches 'Name'"):
        db.execute_query("SELECT Name FROM Data")
    assert db.execute_query("SELECT NAME FROM Data") == [{"NAME": "b"}]


def test_update_unknown_column(make_db):
    db, api = make_db(hobbits())

    with pytest.raises(ColumnNotFoundError, match="'Sheet1' has no column 'Height'"):
        db.execute_query("UPDATE Sheet1 SET Height = 1 WHERE Name = 'Sam'")
    assert "values_batch_update" not in api.calls


# -- results --------------------------------------------------------------------

def test_writes_return_the_number_of_rows_affected(make_db):
    db, _ = make_db(hobbits())

    assert db.execute_query("INSERT INTO Sheet1 (Name) VALUES ('Lobelia'), ('Lotho'), ('Otho')") == 3
    assert db.execute_query("UPDATE Sheet1 SET Home = 'Hardbottle' WHERE Name >= 'Lo' AND Name < 'Lp'") == 2
    assert db.execute_query("UPDATE Sheet1 SET Home = 'Nowhere' WHERE Name = 'Gandalf'") == 0
    assert db.execute_query("DELETE FROM Sheet1 WHERE Home = 'Hardbottle' OR Name = 'Otho'") == 3
    assert db.execute_query("DELETE FROM Sheet1 WHERE Name = 'Otho'") == 0


def test_select_with_no_matches_returns_an_empty_list(make_db):
    db, _ = make_db(hobbits())

    assert db.execute_query("SELECT * FROM Sheet1 WHERE Age > 1000") == []
