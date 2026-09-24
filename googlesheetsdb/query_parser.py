"""
Parses the SQL-like query language into statement objects.

Supported statements (keywords are case-insensitive):

    SELECT * | column [, column ...] FROM table [WHERE condition]
    INSERT INTO table [(column [, column ...])] VALUES (value [, value ...]) [, (...) ...]
    UPDATE table SET column = value [, column = value ...] WHERE condition
    DELETE FROM table WHERE condition

    condition := condition OR condition | condition AND condition | NOT condition
               | (condition) | column operator value | column IS [NOT] NULL
    operator  := = | != | <> | < | <= | > | >=
    value     := 'text' | number | TRUE | FALSE | NULL | ?

Table and column names can be written bare (letters, digits and underscores, not
starting with a digit), or in "double quotes" or `backticks` when they contain spaces or
other characters, or clash with a keyword. Text values go in 'single quotes'. To include
a quote character inside quotes, write it twice.

Each ? is replaced, in order, by the next of the query's parameters. Parameters are
always treated as values, never as query text.
"""
import math
import re
from collections import namedtuple
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .errors import QuerySyntaxError

KEYWORDS = {
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE",
    "AND", "OR", "NOT", "IS", "NULL", "TRUE", "FALSE",
}
OPERATORS = {"=": "=", "!=": "!=", "<>": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}


@dataclass(frozen=True)
class Select:
    table: str
    columns: Optional[Tuple[str, ...]]  # None means SELECT *
    where: Any = None


@dataclass(frozen=True)
class Insert:
    table: str
    columns: Optional[Tuple[str, ...]]  # None means every column, in order
    rows: Tuple[Tuple[Any, ...], ...]


@dataclass(frozen=True)
class Update:
    table: str
    assignments: Tuple[Tuple[str, Any], ...]
    where: Any = None


@dataclass(frozen=True)
class Delete:
    table: str
    where: Any = None


@dataclass(frozen=True)
class Comparison:
    column: str
    operator: str  # one of = != < <= > >=
    value: Any


@dataclass(frozen=True)
class IsNull:
    column: str
    negated: bool = False


@dataclass(frozen=True)
class And:
    left: Any
    right: Any


@dataclass(frozen=True)
class Or:
    left: Any
    right: Any


@dataclass(frozen=True)
class Not:
    condition: Any


def parse(query, params=()):
    """
    Parses one query into a Select, Insert, Update or Delete statement.

    Args:
    - query (str): The query text.
    - params (sequence, optional): Values for the query's ? placeholders, in order.
      Each must be a str, int, float, bool or None.

    Returns:
    - Select | Insert | Update | Delete: The parsed statement.

    Raises:
    - QuerySyntaxError: If the query can't be parsed, or the parameters don't match
      its placeholders.
    """
    if not isinstance(query, str):
        raise QuerySyntaxError(f"The query must be a string, not {type(query).__name__}")
    if isinstance(params, (str, bytes)) or not isinstance(params, Sequence):
        raise QuerySyntaxError("Query parameters must be a list or tuple of values")
    return _Parser(query, params).statement()


_Token = namedtuple("_Token", "kind text position")

_TOKEN_PATTERN = re.compile(r"""
    (?P<space>\s+)
  | (?P<string>'(?:[^']|'')*')
  | (?P<quoted>"(?:[^"]|"")*"|`(?:[^`]|``)*`)
  | (?P<number>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<word>[^\W\d]\w*)
  | (?P<operator><=|>=|<>|!=|=|<|>)
  | (?P<symbol>[(),*;?-])
""", re.VERBOSE)


def _tokenise(query):
    tokens = []
    position = 0
    while position < len(query):
        match = _TOKEN_PATTERN.match(query, position)
        if match is None:
            character = query[position]
            if character in "'\"`":
                raise QuerySyntaxError(f"Unclosed {character} starting at position {position + 1}")
            raise QuerySyntaxError(f"Unexpected character {character!r} at position {position + 1}")
        if match.lastgroup != "space":
            tokens.append(_Token(match.lastgroup, match.group(), position))
        position = match.end()
    tokens.append(_Token("end", "", len(query)))
    return tokens


class _Parser:
    def __init__(self, query, params):
        self.tokens = _tokenise(query)
        self.index = 0
        self.params = list(params)
        self.params_used = 0

    # -- statements -----------------------------------------------------------

    def statement(self):
        if self.accept_keyword("SELECT"):
            statement = self.select()
        elif self.accept_keyword("INSERT"):
            statement = self.insert()
        elif self.accept_keyword("UPDATE"):
            statement = self.update()
        elif self.accept_keyword("DELETE"):
            statement = self.delete()
        else:
            raise self.error("Expected SELECT, INSERT, UPDATE or DELETE")

        self.accept_symbol(";")
        if self.peek().kind != "end":
            raise self.error("Expected the end of the query")
        if self.params_used != len(self.params):
            raise QuerySyntaxError(
                f"The query has {self.params_used} ? placeholder(s) "
                f"but {len(self.params)} parameter(s) were given"
            )
        return statement

    def select(self):
        if self.accept_symbol("*"):
            columns = None
        else:
            columns = self.name_list("a column name or *")
        self.expect_keyword("FROM")
        table = self.name("a table name")
        return Select(table, columns, self.optional_where())

    def insert(self):
        self.expect_keyword("INTO")
        table = self.name("a table name")
        columns = None
        if self.accept_symbol("("):
            columns = self.name_list("a column name")
            self.expect_symbol(")")
        self.expect_keyword("VALUES")
        rows = [self.value_row()]
        while self.accept_symbol(","):
            rows.append(self.value_row())
        return Insert(table, columns, tuple(rows))

    def update(self):
        table = self.name("a table name")
        self.expect_keyword("SET")
        assignments = [self.assignment()]
        while self.accept_symbol(","):
            assignments.append(self.assignment())
        return Update(table, tuple(assignments), self.optional_where())

    def delete(self):
        self.expect_keyword("FROM")
        table = self.name("a table name")
        return Delete(table, self.optional_where())

    def optional_where(self):
        if self.accept_keyword("WHERE"):
            return self.condition()
        return None

    def assignment(self):
        column = self.name("a column name")
        self.expect_operator("=")
        return column, self.value()

    def value_row(self):
        self.expect_symbol("(")
        values = [self.value()]
        while self.accept_symbol(","):
            values.append(self.value())
        self.expect_symbol(")")
        return tuple(values)

    # -- conditions -----------------------------------------------------------

    def condition(self):
        condition = self.and_condition()
        while self.accept_keyword("OR"):
            condition = Or(condition, self.and_condition())
        return condition

    def and_condition(self):
        condition = self.not_condition()
        while self.accept_keyword("AND"):
            condition = And(condition, self.not_condition())
        return condition

    def not_condition(self):
        if self.accept_keyword("NOT"):
            return Not(self.not_condition())
        if self.accept_symbol("("):
            condition = self.condition()
            self.expect_symbol(")")
            return condition
        column = self.name("a column name")
        if self.accept_keyword("IS"):
            negated = bool(self.accept_keyword("NOT"))
            self.expect_keyword("NULL")
            return IsNull(column, negated)
        token = self.peek()
        if token.kind != "operator":
            raise self.error("Expected a comparison operator (=, !=, <>, <, <=, >, >=) or IS")
        self.index += 1
        return Comparison(column, OPERATORS[token.text], self.value())

    # -- names and values -----------------------------------------------------

    def name_list(self, description):
        names = [self.name(description)]
        while self.accept_symbol(","):
            names.append(self.name(description))
        return tuple(names)

    def name(self, description):
        token = self.peek()
        if token.kind == "word" and token.text.upper() not in KEYWORDS:
            self.index += 1
            return token.text
        if token.kind == "quoted":
            self.index += 1
            quote = token.text[0]
            name = token.text[1:-1].replace(quote * 2, quote)
            if not name.strip():
                raise QuerySyntaxError(f"Empty name at position {token.position + 1}")
            return name
        if token.kind == "word":
            raise self.error(f"Expected {description} ({token.text.upper()} is a keyword: "
                             f"write \"{token.text}\" to use it as a name)")
        raise self.error(f"Expected {description}")

    def value(self):
        token = self.peek()
        self.index += 1
        if token.kind == "string":
            return token.text[1:-1].replace("''", "'")
        if token.kind == "number":
            return _number(token.text)
        if token.kind == "symbol" and token.text == "-" and self.peek().kind == "number":
            return -_number(self.tokens[self.next_index()].text)
        if token.kind == "word" and token.text.upper() in ("TRUE", "FALSE", "NULL"):
            return {"TRUE": True, "FALSE": False, "NULL": None}[token.text.upper()]
        if token.kind == "symbol" and token.text == "?":
            return self.next_param()
        self.index -= 1
        if token.kind in ("word", "quoted"):
            raise self.error("Expected a value (text values need 'single quotes')")
        raise self.error("Expected a value")

    def next_param(self):
        number = self.params_used + 1
        if self.params_used >= len(self.params):
            raise QuerySyntaxError(f"No parameter was given for ? number {number}")
        value = self.params[self.params_used]
        self.params_used += 1
        if value is None or isinstance(value, (str, bool, int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise QuerySyntaxError(f"Parameter {number} is {value}, which a sheet can't store")
            return value
        raise QuerySyntaxError(
            f"Parameter {number} is a {type(value).__name__}; "
            "use a str, int, float, bool or None"
        )

    # -- token helpers --------------------------------------------------------

    def peek(self):
        return self.tokens[self.index]

    def next_index(self):
        self.index += 1
        return self.index - 1

    def accept_keyword(self, keyword):
        token = self.peek()
        if token.kind == "word" and token.text.upper() == keyword:
            self.index += 1
            return token
        return None

    def expect_keyword(self, keyword):
        if not self.accept_keyword(keyword):
            raise self.error(f"Expected {keyword}")

    def accept_symbol(self, symbol):
        token = self.peek()
        if token.kind == "symbol" and token.text == symbol:
            self.index += 1
            return token
        return None

    def expect_symbol(self, symbol):
        if not self.accept_symbol(symbol):
            raise self.error(f"Expected {symbol!r}")

    def expect_operator(self, operator):
        token = self.peek()
        if token.kind != "operator" or token.text != operator:
            raise self.error(f"Expected {operator!r}")
        self.index += 1

    def error(self, message):
        token = self.peek()
        found = "the end of the query" if token.kind == "end" else repr(token.text)
        return QuerySyntaxError(f"{message}, but found {found} at position {token.position + 1}")


def _number(text):
    if any(c in text for c in ".eE"):
        return float(text)
    return int(text)
