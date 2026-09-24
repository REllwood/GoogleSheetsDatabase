# Google Sheets Python Library

A very basic Python library that allows you to interact with Google Sheets as a database table using basic SQL-like commands. It provides functionalities for SELECT, INSERT, UPDATE, and DELETE operations on Google Sheets.


## Why?
Great question, when doing very basic development, or running small-scale hobby projects, having the cost of running a DB server can be a bit of a pain. I know there are plenty of free options out there (and these are superior), but I wanted to see if I could use Google Sheets as a database table and here we are. 
## Installation

Requires Python 3.10 or newer. Install the required packages using pip:

```bash
pip install -r requirements.txt
```

This installs [gspread](https://github.com/burnash/gspread) 6 and [google-auth](https://github.com/googleapis/google-auth-library-python).


## Usage

### Setting Up Authentication

First, enable the **Google Sheets API** for your project in the [Google Cloud Console](https://console.cloud.google.com/apis/library/sheets.googleapis.com). Then choose one of the following.

The spreadsheet ID is the long string in your sheet's URL: `https://docs.google.com/spreadsheets/d/<spreadsheet_id>/edit`.

1. **Service account (best for scripts and servers):**
   - Create a service account and download its JSON key file.
   - **Share your Google Sheet with the service account's email address** (the `client_email` value in the key file) and give it Editor access. The service account can't open the sheet until you do this.
   - Pass the path to the key file:
     ```python
     from main_module import GoogleSheetDB

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

Keep key and token files out of git. The included `.gitignore` covers the usual file names.

### Performing Operations

After authentication, you can execute SQL-like commands on your Google Sheets:

- **SELECT Operation:**
  ```python
  result = db.execute_query("SELECT * FROM Sheet1")
  print(result)
    ```
- **INSERT Operation:**
    ```python
    db.execute_query("INSERT INTO Sheet1 (Name, Age) VALUES ('Frodo', 52)")
    ```
- **UPDATE Operation:**
    ```python
    db.execute_query("UPDATE Sheet1 SET Age = 26 WHERE Name = 'Frodo'")
    ```
- **DELETE Operation:**
- ```python
    db.execute_query("DELETE FROM Sheet1 WHERE Name = 'Frodo'")
    ```

## Limitations
This is a very basic implementation of a database using Google Sheets. It is not intended to be used for large-scale applications. Some of the limitations are:
- **Sheet Structure Requirements:**
  - Single header row and column.
  - One table per sheet.
  - Single worksheet allowed.
- **Header Specifications:**
  - Unique values within the header row and column.
  - No empty cells, special characters, spaces, or duplicates in headers.


## Future Work
- **Sheet and Table Management:**
  - Support for multiple tables within a single Google Sheet.
    - Support for multiple worksheets within a single Google Sheet.
      - Ability to create new tables (sheets) and worksheets in a Google Workbook.
- **Header Control:**
  - Allow users to specify multiple header rows and columns.
  - Flexibility to specify the header row and column by index, name, regex, or a combination of values, regex, names, and indices.
  
## Running the Tests

The tests run against an in-memory fake of the Google Sheets API, so they need no Google account or network access:

```bash
pip install -r requirements-dev.txt
pytest
```

## Contributing
Contributions are welcome! Feel free to open issues or submit pull requests for improvements, bug fixes, or additional features.

## License
This project is licensed under the [MIT License](https://choosealicense.com/licenses/mit/)

## Author
[Rhys Ellwood](https://github.com/REllwood)