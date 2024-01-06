# Google Sheets Python Library

A very basic Python library that allows you to interact with Google Sheets as a database table using basic SQL-like commands. It provides functionalities for SELECT, INSERT, UPDATE, and DELETE operations on Google Sheets.


## Why?
Great question, when doing very basic development, or running small-scale hobby projects, having the cost of running a DB server can be a bit of a pain. I know there are plenty of free options out there (and these are superior), but I wanted to see if I could use Google Sheets as a database table and here we are. 
## Installation

Install the required packages using pip:

```bash
pip install gspread oauth2client
```


## Usage

### Setting Up Authentication

1. **Obtain OAuth2 Credentials:**
   - Create OAuth2 credentials in the [Google Cloud Console](https://console.cloud.google.com/).
   - Get the client ID and client secret.

2. **initialise GoogleSheetDB with Service Account Credentials (Optional):**
   - If using a service account, download the service account credentials JSON file.
   - Import `GoogleSheetDB` from `main_module.py`.
   - Create an instance of `GoogleSheetDB` by passing your Google Sheet ID and the path to the service account credentials file:
     ```python
     from main_module import GoogleSheetDB

     spreadsheet_id = 'YOUR_SPREADSHEET_ID'
     credentials_file = 'path/to/your/credentials.json'  # Path to your serviceaccount credentials file
     db = GoogleSheetDB(spreadsheet_id, credentials_file)
     ```

3. **initialise GoogleSheetDB with Default Credentials:**
   - If not using a service account, you can initialise `GoogleSheetDB` without providing a credentials file. This will attempt to use the application default credentials:
     ```python
     db = GoogleSheetDB('YOUR_SPREADSHEET_ID')  # Initialises GoogleSheetDB using default credentials
     ```

4. **Authenticate User (if using default credentials):**
   - Use the `authenticate` method to initiate the OAuth2 flow if you are using default credentials:
     ```python
     db.authenticate()
     ```
   - Follow the prompts to authorize access and enter the obtained authorization code.

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
  
## Contributing
Contributions are welcome! Feel free to open issues or submit pull requests for improvements, bug fixes, or additional features.

## License
This project is licensed under the [MIT License](https://choosealicense.com/licenses/mit/)

## Author
[Rhys Ellwood](https://github.com/REllwood)