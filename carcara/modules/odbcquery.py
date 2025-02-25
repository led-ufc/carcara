#! python3
import pyodbc
import base64  # for encoding/decoding the password

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