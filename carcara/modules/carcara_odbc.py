#! python3
import pyodbc
import base64  # for encoding/decoding the password
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path

def unencode_password(cstring):
    """
    Decodes the base64 encoded password in the connection string.
    Expects the password to be specified in the connection string as:
       Pwd=<base64_encoded_value>
    """
    parts = cstring.split(";")
    new_parts = []
    for part in parts:
        part = part.strip()
        if part.lower().startswith("pwd="):
            # Extract the encoded password (everything after "Pwd=")
            encoded = part[4:].strip()
            try:
                decoded = base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
            except Exception as e:
                print("Error decoding password:", e)
                decoded = encoded
            new_parts.append("Pwd=" + decoded)
        else:
            new_parts.append(part)
    return "; ".join(new_parts)

def run_query(CToggle, CString, Query):
    """
    Executes a database query using pyodbc based on the provided parameters.
    
    Parameters:
        CToggle (bool): Flag indicating whether to attempt a connection.
        CString (str): Database connection string, where the password is base64 encoded.
        Query (str): The SQL query to execute.
        
    Returns:
        QResult: For data-retrieval queries, a list of values (one per row, for the first column)
                 for non-data queries, a confirmation message.
                 If CToggle is False or an error occurs, returns an empty string.
    """
    QResult = ""
    if not CToggle:
        print("Error: 'CToggle' is False. No connection will be attempted.")
        return QResult

    connection = None
    cursor = None

    try:
        # Decode the password from the connection string
        decoded_cstring = unencode_password(CString)
        connection = pyodbc.connect(decoded_cstring, timeout=0)
        cursor = connection.cursor()

        # Execute the query
        cursor.execute(Query)
        # If the query starts with 'select', 'show', or 'describe', fetch results
        if Query.strip().lower().startswith(('select', 'show', 'describe')):
            rawResult = cursor.fetchall()
            # Extract the first column of each row into a simple list
            QResult = [row[0] for row in rawResult]
        else:
            connection.commit()
            QResult = "Review the query"
    except pyodbc.DatabaseError as db_error:
        print(f"Error executing the query: {db_error}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return QResult
    
    
def run_command(CToggle, CString, Command):
    """
    Executes a non-data command (e.g., DDL or DML) using pyodbc.
    
    Parameters:
        CToggle (bool): Flag indicating whether to attempt a connection.
        CString (str): Database connection string, with the password base64 encoded.
        Command (str): The SQL command to execute.
        
    Returns:
        A formatted string containing:
          - Success: True/False
          - Rows Affected: (number of rows affected, if available)
          - Message: Detailed message or error information.
    """
    result_info = {"success": False, "rows_affected": None, "message": ""}
    
    if not CToggle:
        result_info["message"] = "CToggle is False. No connection was attempted."
        return "Success: {}\nRows Affected: {}\nMessage: {}".format(
            result_info["success"], result_info["rows_affected"], result_info["message"]
        )

    connection = None
    cursor = None

    try:
        # Decode the password from the connection string
        decoded_cstring = unencode_password(CString)
        connection = pyodbc.connect(decoded_cstring, timeout=0)
        cursor = connection.cursor()

        # Execute the command
        cursor.execute(Command)
        
        # Get the number of rows affected
        affected = cursor.rowcount
        
        # Commit the transaction
        connection.commit()

        result_info["success"] = True
        result_info["rows_affected"] = affected
        result_info["message"] = "Command executed successfully."
    except pyodbc.DatabaseError as db_error:
        result_info["message"] = "Database error: {}".format(db_error)
    except Exception as e:
        result_info["message"] = "Unexpected error: {}".format(e)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    # Return a formatted string with the feedback
    return "Success: {}\nRows Affected: {}\nMessage: {}".format(
        result_info["success"], result_info["rows_affected"], result_info["message"]
    )
    
def run_query_to_tree(CToggle, CString, Query):
    """
    Executes a SQL query and returns a DataTree where:
      - Branch 0 contains all values of column 0,
      - Branch 1 contains all values of column 1,
      - …and so on.
    """
    # 1. Early exit if toggle is off
    if not CToggle:
        return DataTree[object]()
    
    # 2. Connect & fetch
    decoded = unencode_password(CString)
    conn = pyodbc.connect(decoded, timeout=0)
    cur  = conn.cursor()
    cur.execute(Query)
    rows = cur.fetchall()   # List of tuples
    conn.commit()
    cur.close()
    conn.close()
    
    # 3. If no rows, return empty tree
    if not rows:
        return DataTree[object]()
    
    # 4. Determine number of columns
    n_cols = len(rows[0])
    
    # 5. Build DataTree
    tree = DataTree[object]()
    for col_idx in range(n_cols):
        path = GH_Path(col_idx)               # branch index = column index
        for row in rows:
            tree.Add(row[col_idx], path)     # add each row’s col_idx value
    
    return tree
