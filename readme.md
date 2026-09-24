# Google Sheets Python Library

A small Python library that lets you use a Google Sheet as a database, with familiar SQL-like `SELECT`, `INSERT`, `UPDATE` and `DELETE` queries.

```python
from googlesheetsdb import GoogleSheetDB

db = GoogleSheetDB('YOUR_SPREADSHEET_ID', 'service-account.json')

db.execute_query("INSERT INTO Hobbits (Name, Age) VALUES ('Frodo', 50)")
db.execute_query("SELECT Name, Age FROM Hobbits WHERE Age > 30")
# [{'Name': 'Frodo', 'Age': 50}]
```


## Why?
Great question, when doing very basic development, or running small-scale hobby projects, having the cost of running a DB server can be a bit of a pain. I know there are plenty of free options out there (and these are superior), but I wanted to see if I could use Google Sheets as a database table and here we are.

## Installation

Requires Python 3.10 or newer. Install straight from GitHub with pip:

```bash
pip install git+https://github.com/REllwood/GoogleSheetsDatabase.git
```

This also installs [gspread](https://github.com/burnash/gspread) 6 and [google-auth](https://github.com/googleapis/google-auth-library-python).


## Setting Up Authentication

First, enable the **Google Sheets API** for your project in the [Google Cloud Console](https://console.cloud.google.com/apis/library/sheets.googleapis.com). Then choose one of the following.

The spreadsheet ID is the long string in your sheet's URL: `https://docs.google.com/spreadsheets/d/<spreadsheet_id>/edit`.

1. **Service account (best for scripts and servers):**
   - Create a service account and download its JSON key file.
   - **Share your Google Sheet with the service account's email address** (the `client_email` value in the key file) and give it Editor access. The service account can't open the sheet until you do this.
   - Pass the path to the key file:
     ```python
     from googlesheetsdb import GoogleSheetDB

     db = GoogleSheetDB('YOUR_SPREADSHEET_ID', 'path/to/service-account.json')
     ```

2. **Your own Google account (OAuth):**
   - Create an OAuth client ID of type *Desktop app* and download its JSON file.
   - Use `from_oauth`. The first run opens your browser so you can sign in and grant access; the token is then saved (by default to `~/.config/gspread/authorized_user.json`) and reused:
     ```python
     db = GoogleSheetDB.from_oauth('YOUR_SPREADSHEET_ID', 'path/to/client_secret.json')
     ```

3. **Application Default Credentials:**
   - Leave out the key file:
     ```python
     db = GoogleSheetDB('YOUR_SPREADSHEET_ID')
     ```
   - On Google Cloud (Cloud Run, Compute Engine and so on) this uses the attached service account; share the sheet with it as in option 1.
   - On your own machine, sign in with the Sheets scope first:
     ```bash
     gcloud auth application-default login --scopes=https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/cloud-platform
     ```
     If Google then says the Sheets API needs a quota project, run `gcloud auth application-default set-quota-project YOUR_PROJECT_ID`.

If you already have an authorised gspread client, pass it instead: `GoogleSheetDB('YOUR_SPREADSHEET_ID', client=gc)`.

Keep key and token files out of git. The included `.gitignore` covers the usual file names.


## Laying Out Your Sheet

- Each worksheet (tab) is a table, and the tab's name is the table's name.
- Row 1 holds the column names. Every row below it is a record.
- Each column name must be unique within its tab. Columns with nothing in row 1 are ignored.
- Completely empty rows are skipped.

For example, a tab named `Hobbits`:

| Name   | Age | Home        |
|--------|-----|-------------|
| Frodo  | 50  | Bag End     |
| Sam    | 38  | Bagshot Row |
| Pippin | 28  | Tuckborough |


## Queries

`db.execute_query(query, params=())` runs one query. Keywords such as `SELECT` or `where` can be written in any case; table names, column names and values keep theirs. A trailing `;` is optional.

### SELECT

```python
db.execute_query("SELECT * FROM Hobbits")
db.execute_query("SELECT Name, Home FROM Hobbits WHERE Age >= 33")
# [{'Name': 'Frodo', 'Home': 'Bag End'}, {'Name': 'Sam', 'Home': 'Bagshot Row'}]
```

Returns a list with a dictionary for each matching row. `SELECT *` gives every column, in sheet order; otherwise you get the columns you list, in the order you list them.

### INSERT

```python
db.execute_query("INSERT INTO Hobbits (Name, Age) VALUES ('Merry', 36)")
db.execute_query("INSERT INTO Hobbits (Name, Age) VALUES ('Lobelia', 90), ('Lotho', 50)")
db.execute_query("INSERT INTO Hobbits VALUES ('Bilbo', 111, 'Rivendell')")
```

Values go into the columns you list, matched by name, and any other columns are left blank. Without a column list, give a value for every column, from left to right. New rows are added below the last row of the table.

Returns the number of rows inserted.

### UPDATE

```python
db.execute_query("UPDATE Hobbits SET Age = 51, Home = 'Rivendell' WHERE Name = 'Frodo'")
```

Returns the number of rows updated. `SET Column = NULL` clears a cell.

### DELETE

```python
db.execute_query("DELETE FROM Hobbits WHERE Home IS NULL")
```

Returns the number of rows deleted.

`UPDATE` and `DELETE` need a `WHERE` clause, so a slip can't overwrite or delete a whole table.

### WHERE Conditions

| Condition | Matches rows where |
|---|---|
| `Age = 38`, `Age != 38` (or `Age <> 38`) | the value is, or isn't, equal |
| `Age < 30`, `Age <= 30`, `Age > 30`, `Age >= 30` | the value is less or greater |
| `Home IS NULL`, `Home IS NOT NULL` | the cell is, or isn't, blank |
| `Age > 30 AND Home = 'Bag End'` | both conditions are true |
| `Name = 'Sam' OR Name = 'Frodo'` | either condition is true |
| `NOT (Age > 30)` | the condition is false |

`AND` is applied before `OR`; use brackets to change that, as in `(A OR B) AND C`.

Text comparisons are case-sensitive, so `Name = 'frodo'` doesn't match `Frodo`.

### Writing Names and Values

- **Text** goes in single quotes: `'Bag End'`. For a single quote inside text, write two: `'O''Brien'`.
- **Numbers** are written as they are: `42`, `-7`, `3.5`.
- **Booleans** are `TRUE` and `FALSE`, and **blank** is `NULL`.
- **Table and column names** that contain spaces or other characters, or that are keywords such as `Values`, go in double quotes or backticks: `SELECT "First Name" FROM "Team List"`.
- Table and column names are matched exactly first, then ignoring upper and lower case.

### Parameters

For any value that comes from outside your code (user input, form fields, files), put a `?` in the query and pass the values separately, in order:

```python
db.execute_query("SELECT * FROM Hobbits WHERE Name = ? AND Age > ?", [name, min_age])
db.execute_query("INSERT INTO Hobbits (Name, Age) VALUES (?, ?)", ("Farmer Maggot", 70))
```

Parameters are only ever used as values, never read as part of the query, so they can't change what the query does (SQL injection). Each must be a `str`, `int`, `float`, `bool` or `None`.


## Values and Types

Values keep their type on the way in and out:

| In the sheet | In Python |
|---|---|
| Number, including percentages and currency | `int` or `float`: the underlying number, so `50%` is `0.5` |
| TRUE/FALSE or a checkbox | `bool` |
| Text | `str`, exactly as stored: a postcode such as `'0800'` keeps its leading zero |
| Blank cell | `None` |
| Date or time | `str`, formatted as in the sheet |

Text you write is stored exactly as given. It's never turned into a number, date or formula, so `'0800'` stays text and `'=SUM(A:A)'` is stored as text rather than run. Write `800` without quotes to store a number.

In `WHERE`, values compare with cells of the same type. Text and numbers only compare when the text is written exactly like a number: `Age = '38'` matches `38`, but `Postcode = 800` doesn't match `'0800'`.

A blank cell matches `IS NULL` (and `= NULL`) but never equals a value. So `Home != 'Bag End'` includes rows with a blank home, while `Age > 30` skips rows with a blank age.

Dates are compared as text, so they only sort correctly when written year first, such as `2026-09-24`.


## Results and Errors

`SELECT` returns a list of dictionaries. `INSERT`, `UPDATE` and `DELETE` return the number of rows they changed.

Problems raise an exception. Every problem with a query is a `QueryError`, so you can catch them all at once:

| Exception | Raised when |
|---|---|
| `QuerySyntaxError` | The query can't be understood, or the parameters don't match its `?`s. Nothing is sent to Google. |
| `TableNotFoundError` | No worksheet has the table's name. |
| `ColumnNotFoundError` | A column isn't in the table's header row. |
| `QueryError` | Anything else wrong with the query, such as an `UPDATE` without `WHERE`. |
| `gspread.exceptions.APIError` | Google rejected the request, for example because of permissions or rate limits. |

```python
from googlesheetsdb import QueryError

try:
    deleted = db.execute_query("DELETE FROM Hobbits WHERE Name = ?", [name])
except QueryError as error:
    print(f"That query didn't work: {error}")
```

Error messages say what went wrong and where, such as `Expected FROM, but found 'Hobbits' at position 10` or `'Hobbits' has no column 'Height'. Columns: 'Name', 'Age', 'Home'`.


## Limitations
This is a small library for small tables, not a replacement for a real database:
- **Size and speed:** every query reads the whole worksheet, and Google limits how many requests you can make each minute. It suits hundreds or a few thousand rows, not millions.
- **No locking:** if two programs change the same sheet at the same time, one can overwrite the other's changes, or an `UPDATE` or `DELETE` can act on rows that moved in between. Have only one program write to a sheet at a time.
- **Query features:** there are no joins, `ORDER BY`, `LIMIT`, `GROUP BY` or `LIKE`. Sort and filter the returned list in Python instead.
- **Layout:** one table per worksheet, with its column names in row 1.


## Future Work
- `ORDER BY`, `LIMIT`, `LIKE` and `IN`.
- Creating tables (worksheets) from a query.
- **Header Control:**
  - Allow users to specify multiple header rows and columns.
  - Flexibility to specify the header row and column by index, name, regex, or a combination of values, regex, names, and indices.
  - Support for multiple tables within a single worksheet.


## Upgrading From the First Version
- Import from `googlesheetsdb`. The old `from main_module import GoogleSheetDB` still works from a checkout of this repository.
- Errors are raised as exceptions instead of being returned as strings, and `INSERT`, `UPDATE` and `DELETE` return row counts instead of messages such as `"Insertion successful"`.
- Text values need single quotes, and are no longer converted to capitals.
- `UPDATE` now needs a `WHERE` clause, like `DELETE`.
- Sign in as a Google user with `GoogleSheetDB.from_oauth(...)`. The `authenticate()` method in the old README never existed.


## Running the Tests

The tests run against an in-memory fake of the Google Sheets API, so they need no Google account or network access:

```bash
pip install -e ".[dev]"
pytest
```

To also test against a real Google Sheet, point these environment variables at a spreadsheet the tests can write to, and a service account key with Editor access to it. Each test works in a new worksheet and deletes it afterwards.

```bash
export GOOGLESHEETSDB_TEST_SPREADSHEET_ID=your-spreadsheet-id
export GOOGLESHEETSDB_TEST_CREDENTIALS=path/to/service-account.json
pytest tests/test_live.py
```

## Contributing
Contributions are welcome! Feel free to open issues or submit pull requests for improvements, bug fixes, or additional features.

## License
This project is licensed under the [MIT License](https://choosealicense.com/licenses/mit/)

## Author
[Rhys Ellwood](https://github.com/REllwood)
