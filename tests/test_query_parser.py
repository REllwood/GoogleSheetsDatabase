import pytest

from googlesheetsdb.errors import QuerySyntaxError
from googlesheetsdb.query_parser import (
    And, Comparison, Delete, Insert, IsNull, Not, Or, Select, Update, parse,
)


# -- statements ---------------------------------------------------------------

def test_select_star():
    assert parse("SELECT * FROM Sheet1") == Select("Sheet1", None, None)


def test_select_columns_and_where():
    assert parse("select Name, Age from Hobbits where Age >= 33") == Select(
        "Hobbits", ("Name", "Age"), Comparison("Age", ">=", 33)
    )


def test_insert_with_columns_and_several_rows():
    assert parse("INSERT INTO Sheet1 (Name, Age) VALUES ('Frodo', 50), ('Sam', 38)") == Insert(
        "Sheet1", ("Name", "Age"), (("Frodo", 50), ("Sam", 38))
    )


def test_insert_without_columns():
    assert parse("INSERT INTO Sheet1 VALUES ('Frodo', 50)") == Insert("Sheet1", None, (("Frodo", 50),))


def test_update_with_several_assignments():
    assert parse("UPDATE Sheet1 SET Age = 51, Home = 'Bag End' WHERE Name = 'Frodo'") == Update(
        "Sheet1", (("Age", 51), ("Home", "Bag End")), Comparison("Name", "=", "Frodo")
    )


def test_delete():
    assert parse("DELETE FROM Sheet1 WHERE Name = 'Sam'") == Delete("Sheet1", Comparison("Name", "=", "Sam"))


def test_update_and_delete_parse_without_where():
    assert parse("UPDATE T SET A = 1").where is None
    assert parse("DELETE FROM T").where is None


# -- case, whitespace and punctuation -----------------------------------------

def test_keywords_are_case_insensitive_but_names_and_values_keep_their_case():
    assert parse("sElEcT Name FrOm MyTab WhErE Name = 'Frodo Baggins'") == Select(
        "MyTab", ("Name",), Comparison("Name", "=", "Frodo Baggins")
    )


def test_any_whitespace_and_a_trailing_semicolon():
    assert parse("\n  SELECT   *\n\tFROM  Sheet1 ;  ") == Select("Sheet1", None, None)


def test_values_may_contain_sql_punctuation_and_keywords():
    statement = parse("INSERT INTO T VALUES ('a=b, (c); WHERE d', 'O''Brien')")
    assert statement.rows == (("a=b, (c); WHERE d", "O'Brien"),)


def test_quoted_names_allow_spaces_quotes_and_keywords():
    statement = parse('SELECT "First Name", `Where`, "Say ""hi""" FROM "My Sheet" WHERE "Age (years)" > 3')
    assert statement == Select(
        "My Sheet", ("First Name", "Where", 'Say "hi"'), Comparison("Age (years)", ">", 3)
    )


def test_unicode_names():
    assert parse("SELECT Größe FROM Café").columns == ("Größe",)


# -- values -------------------------------------------------------------------

@pytest.mark.parametrize("text, value", [
    ("42", 42),
    ("-7", -7),
    ("3.5", 3.5),
    ("-0.25", -0.25),
    (".5", 0.5),
    ("1e3", 1000.0),
    ("TRUE", True),
    ("false", False),
    ("NULL", None),
    ("''", ""),
    ("'0800'", "0800"),
])
def test_value_literals(text, value):
    (row,) = parse(f"INSERT INTO T VALUES ({text})").rows
    assert row == (value,)
    assert type(row[0]) is type(value)


# -- conditions ---------------------------------------------------------------

@pytest.mark.parametrize("operator, normalised", [
    ("=", "="), ("!=", "!="), ("<>", "!="), ("<", "<"), ("<=", "<="), (">", ">"), (">=", ">="),
])
def test_comparison_operators(operator, normalised):
    assert parse(f"SELECT * FROM T WHERE A {operator} 1").where == Comparison("A", normalised, 1)


def test_and_binds_tighter_than_or():
    assert parse("SELECT * FROM T WHERE A = 1 OR B = 2 AND C = 3").where == Or(
        Comparison("A", "=", 1), And(Comparison("B", "=", 2), Comparison("C", "=", 3))
    )


def test_parentheses_and_not():
    assert parse("SELECT * FROM T WHERE NOT (A = 1 OR B = 2) AND C IS NOT NULL").where == And(
        Not(Or(Comparison("A", "=", 1), Comparison("B", "=", 2))), IsNull("C", negated=True)
    )


def test_is_null():
    assert parse("DELETE FROM T WHERE A IS NULL").where == IsNull("A")


# -- parameters ---------------------------------------------------------------

def test_parameters_fill_placeholders_in_order():
    statement = parse("UPDATE T SET A = ?, B = ? WHERE C = ?", ["x", 2, None])
    assert statement == Update("T", (("A", "x"), ("B", 2)), Comparison("C", "=", None))


def test_parameters_are_never_parsed_as_query_text():
    statement = parse("DELETE FROM T WHERE Name = ?", ("x' OR '1'='1",))
    assert statement.where == Comparison("Name", "=", "x' OR '1'='1")


@pytest.mark.parametrize("query, params, message", [
    ("SELECT * FROM T WHERE A = ?", (), "No parameter was given for ? number 1"),
    ("SELECT * FROM T WHERE A = ?", (1, 2), "1 ? placeholder(s) but 2 parameter(s)"),
    ("SELECT * FROM T", ("x",), "0 ? placeholder(s) but 1 parameter(s)"),
    ("SELECT * FROM T WHERE A = ?", ([1],), "Parameter 1 is a list"),
    ("SELECT * FROM T WHERE A = ?", (float("nan"),), "Parameter 1 is nan"),
    ("SELECT * FROM T WHERE A = ?", "x", "must be a list or tuple"),
])
def test_bad_parameters(query, params, message):
    with pytest.raises(QuerySyntaxError, match=message.replace("?", r"\?").replace("(", r"\(").replace(")", r"\)")):
        parse(query, params)


# -- syntax errors ------------------------------------------------------------

@pytest.mark.parametrize("query, message", [
    ("DROP TABLE Sheet1", "Expected SELECT, INSERT, UPDATE or DELETE, but found 'DROP' at position 1"),
    ("", "Expected SELECT, INSERT, UPDATE or DELETE, but found the end of the query"),
    ("SELECT * Sheet1", "Expected FROM, but found 'Sheet1' at position 10"),
    ("SELECT Name, FROM Sheet1", "Expected a column name or \\*"),
    ("SELECT * FROM Sheet1 WHERE Name = Frodo", "Expected a value \\(text values need 'single quotes'\\)"),
    ('SELECT * FROM Sheet1 WHERE Name = "Frodo"', "text values need 'single quotes'"),
    ("SELECT * FROM Sheet1 WHERE Name = 'Frodo", "Unclosed ' starting at position 35"),
    ("SELECT * FROM Sheet1 WHERE Age > 30 30", "Expected the end of the query, but found '30'"),
    ("SELECT * FROM Sheet1 WHERE Age", "Expected a comparison operator"),
    ("SELECT * FROM Sheet1 WHERE Age IS 3", "Expected NULL"),
    ("SELECT * FROM Sheet1 WHERE (Age = 3", "Expected '\\)'"),
    ("SELECT * FROM Values", "VALUES is a keyword: write \"Values\" to use it as a name"),
    ("SELECT * FROM Sheet1 WHERE Age = 3 # comment", "Unexpected character '#' at position 36"),
    ("INSERT INTO T (A) VALUES", "Expected '\\('"),
    ("UPDATE T SET A 1", "Expected '='"),
    ("SELECT * FROM T WHERE A = )", "Expected a value, but found '\\)'"),
    ("SELECT * FROM T WHERE A = -'x'", "Expected a value, but found '-'"),
    ('SELECT "" FROM T', "Empty name at position 8"),
])
def test_syntax_errors(query, message):
    with pytest.raises(QuerySyntaxError, match=message):
        parse(query)


def test_query_must_be_a_string():
    with pytest.raises(QuerySyntaxError, match="must be a string"):
        parse(None)
