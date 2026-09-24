"""Values keep their type on the way into and out of the sheet."""
import pytest

from googlesheetsdb.sheet_table import _number_from_text


def contacts():
    return {"Contacts": [
        ["Name", "Postcode", "Age", "Member", "Discount", "Joined"],
        ["Ada", "0800", 36, True, 0.5, "2026-01-31"],
        ["Bob", "3000", 52, False, "", "2025-12-01"],
        ["Cy", "52", "", "", 0.125, ""],
    ]}


def test_select_returns_typed_values_and_none_for_blanks(make_db):
    db, _ = make_db(contacts())

    assert db.execute_query("SELECT * FROM Contacts") == [
        {"Name": "Ada", "Postcode": "0800", "Age": 36, "Member": True, "Discount": 0.5, "Joined": "2026-01-31"},
        {"Name": "Bob", "Postcode": "3000", "Age": 52, "Member": False, "Discount": None, "Joined": "2025-12-01"},
        {"Name": "Cy", "Postcode": "52", "Age": None, "Member": None, "Discount": 0.125, "Joined": None},
    ]


def test_reads_underlying_values_with_dates_as_text(make_db):
    db, api = make_db(contacts())

    db.execute_query("SELECT * FROM Contacts")

    assert api.values_get_params[-1]["valueRenderOption"] == "UNFORMATTED_VALUE"
    assert api.values_get_params[-1]["dateTimeRenderOption"] == "FORMATTED_STRING"


@pytest.mark.parametrize("where, names", [
    ("Postcode = '0800'", ["Ada"]),
    ("Postcode = 800", []),
    ("Postcode = 3000", ["Bob"]),
    ("Postcode > 1000", ["Bob"]),
    ("Age = '36'", ["Ada"]),
    ("Age > '40'", ["Bob"]),
    ("Age = 'thirty-six'", []),
    ("Member = TRUE", ["Ada"]),
    ("Member = FALSE", ["Bob"]),
    ("Member = 1", []),
    ("Member = 'TRUE'", []),
    ("Member IS NULL", ["Cy"]),
    ("Discount = 0.5", ["Ada"]),
    ("Discount < 0.2", ["Cy"]),
    ("Joined >= '2026-01-01'", ["Ada"]),
])
def test_comparisons_respect_types(make_db, where, names):
    db, _ = make_db(contacts())

    rows = db.execute_query(f"SELECT Name FROM Contacts WHERE {where}")

    assert [row["Name"] for row in rows] == names


def test_leading_zeros_survive_a_round_trip(make_db):
    db, api = make_db(contacts())

    db.execute_query("INSERT INTO Contacts (Name, Postcode) VALUES ('Dee', '0870')")

    assert api.values("Contacts")[-1] == ["Dee", "0870"]
    assert db.execute_query("SELECT Postcode FROM Contacts WHERE Name = 'Dee'") == [{"Postcode": "0870"}]


def test_inserted_values_keep_their_types(make_db):
    db, _ = make_db(contacts())

    db.execute_query(
        "INSERT INTO Contacts (Name, Postcode, Age, Member, Discount) VALUES (?, ?, ?, ?, ?)",
        ("Eve", "0200", 41, True, 0.1),
    )

    assert db.execute_query("SELECT * FROM Contacts WHERE Name = 'Eve'") == [
        {"Name": "Eve", "Postcode": "0200", "Age": 41, "Member": True, "Discount": 0.1, "Joined": None},
    ]


def test_updated_values_keep_their_types(make_db):
    db, api = make_db(contacts())

    db.execute_query("UPDATE Contacts SET Postcode = '0000', Member = FALSE, Age = 37 WHERE Name = 'Ada'")

    assert api.values("Contacts")[1][:4] == ["Ada", "0000", 37, False]


def test_numeric_header_names_are_read_as_text(make_db):
    db, _ = make_db({"Sales": [["Region", 2025, 2026], ["North", 10, 12]]})

    assert db.execute_query('SELECT "2026" FROM Sales WHERE Region = \'North\'') == [{"2026": 12}]


def test_true_false_header_names_are_read_as_text(make_db):
    db, _ = make_db({"Flags": [["Name", True], ["x", 1]]})

    assert db.execute_query("SELECT * FROM Flags") == [{"Name": "x", "TRUE": 1}]


@pytest.mark.parametrize("text, number", [
    ("38", 38), (" 38 ", 38), ("-2.5", -2.5), ("2.50", 2.5), ("0", 0), ("0.75", 0.75),
    ("0800", None), ("1e3", None), ("+5", None), ("5.", None), ("", None), ("12 Main St", None),
    ("9" * 400, None),
])
def test_number_from_text(text, number):
    result = _number_from_text(text)
    assert result == number
    assert type(result) is type(number)
