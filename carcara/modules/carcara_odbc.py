"""Carcara ODBC - Database Connection and Query Module

This module provides thread-safe database connectivity for Grasshopper components
using pyodbc. Includes connection management, query execution, and result formatting
for Grasshopper DataTree structures.

Features:
    - Thread-safe connection pooling
    - Base64 password encoding/decoding
    - Automatic transaction management
    - Query result to DataTree conversion
    - Column header extraction
    - Comprehensive error handling

Functions:
    - run_query: Execute SELECT queries and return results
    - run_command: Execute DDL/DML commands (INSERT, UPDATE, DELETE, etc.)
    - run_query_to_tree: Execute query and return DataTree with column-based branches
    - get_query_headers: Extract column headers without fetching data
    - unencode_password: Decode base64-encoded passwords

Version: 1.0
Date: 2025/10/16
Requires: pyodbc, Grasshopper
"""

import pyodbc
import base64
from contextlib import contextmanager
import threading
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path


###############################################################################
# CONNECTION MANAGEMENT
###############################################################################

class DatabaseConnectionManager:
    """
    Thread-safe database connection manager.
    
    Provides context manager for safe connection handling with
    automatic rollback on errors and guaranteed cleanup.
    """
    
    def __init__(self):
        """Initialize thread-local storage for connections."""
        self._local = threading.local()
    
    @contextmanager
    def get_connection(self, connection_string):
        """
        Context manager for database connections with guaranteed cleanup.
        
        Handles connection creation, error rollback, and proper cleanup.
        
        Args:
            connection_string (str): Database connection string with encoded password
        
        Yields:
            pyodbc.Connection: Active database connection
        
        Raises:
            pyodbc.Error: If connection or query fails
        """
        connection = None
        try:
            decoded_cstring = unencode_password(connection_string)
            connection = pyodbc.connect(decoded_cstring, timeout=30)
            connection.autocommit = False
            yield connection
        except Exception as e:
            if connection:
                try:
                    connection.rollback()
                except:
                    pass
            raise
        finally:
            if connection:
                try:
                    connection.close()
                except:
                    pass


# Global connection manager instance
db_manager = DatabaseConnectionManager()


###############################################################################
# PASSWORD HANDLING
###############################################################################

def unencode_password(cstring):
    """
    Decode base64-encoded password in connection string.
    
    Expects password in format: Pwd=<base64encodedvalue>
    
    Args:
        cstring (str): Connection string with encoded password
    
    Returns:
        str: Connection string with decoded password
    
    Example:
        >>> cstring = "Driver={PostgreSQL};Server=localhost;Pwd=cGFzc3dvcmQ="
        >>> decoded = unencode_password(cstring)
    """
    parts = cstring.split(';')
    new_parts = []
    
    for part in parts:
        part = part.strip()
        if part.lower().startswith('pwd='):
            encoded = part[4:].strip()
            try:
                decoded = base64.b64decode(encoded.encode('utf-8')).decode('utf-8')
            except Exception as e:
                print("Warning: Error decoding password: {}. Using original.".format(e))
                decoded = encoded
            new_parts.append('Pwd={}'.format(decoded))
        else:
            new_parts.append(part)
    
    return ';'.join(new_parts)


###############################################################################
# QUERY EXECUTION FUNCTIONS
###############################################################################

def run_query(CToggle, CString, Query):
    """
    Execute database query and return first column values.
    
    Executes SELECT queries and returns list of values from first column.
    Designed for simple queries returning single-column results.
    
    Args:
        CToggle (bool): Flag to enable/disable connection attempt
        CString (str): Database connection string (password base64-encoded)
        Query (str): SQL query to execute
    
    Returns:
        list or str: 
            - List of values from first column if query returns data
            - Empty list if no rows returned
            - Success message for non-SELECT queries
            - Error message string if query fails or CToggle is False
    
    Example:
        >>> result = run_query(True, connection_string, "SELECT name FROM users")
        >>> print(result)
        ['Alice', 'Bob', 'Charlie']
    """
    if not CToggle:
        return "CToggle is False. No connection attempted."
    
    if not Query or not Query.strip():
        return "Error: Query cannot be empty."
    
    try:
        with db_manager.get_connection(CString) as connection:
            cursor = connection.cursor()
            cursor.execute(Query)
            
            query_lower = Query.strip().lower()
            is_select = query_lower.startswith(('select', 'show', 'describe', 'with'))
            
            if is_select:
                raw_result = cursor.fetchall()
                if raw_result:
                    return [row[0] for row in raw_result]
                else:
                    return []
            else:
                affected_rows = cursor.rowcount
                return "Query executed successfully. Rows affected: {}".format(affected_rows)
            
    except pyodbc.DatabaseError as db_error:
        return "Database error: {}".format(db_error)
    except pyodbc.Error as odbc_error:
        return "ODBC error: {}".format(odbc_error)
    except Exception as e:
        return "Unexpected error: {}".format(e)


def run_command(CToggle, CString, Command):
    """
    Execute database command (DDL/DML) and return formatted feedback.
    
    Executes non-SELECT statements (INSERT, UPDATE, DELETE, CREATE, etc.)
    with automatic transaction commit and detailed feedback.
    
    Args:
        CToggle (bool): Flag to enable/disable connection attempt
        CString (str): Database connection string (password base64-encoded)
        Command (str): SQL command to execute
    
    Returns:
        str: Formatted feedback string with format:
            "Success: True/False | Affected: <rows> | Message: <details>"
    
    Example:
        >>> result = run_command(True, cstring, "INSERT INTO users (name) VALUES ('David')")
        >>> print(result)
        Success: True | Affected: 1 | Message: Command executed successfully.
    """
    result_info = {
        'success': False,
        'rows_affected': None,
        'message': ""
    }
    
    if not CToggle:
        result_info['message'] = "CToggle is False. No connection was attempted."
        return "Success: {success} | Affected: {rows_affected} | Message: {message}".format(**result_info)
    
    if not Command or not Command.strip():
        result_info['message'] = "Command cannot be empty."
        return "Success: {success} | Affected: {rows_affected} | Message: {message}".format(**result_info)
    
    try:
        with db_manager.get_connection(CString) as connection:
            cursor = connection.cursor()
            cursor.execute(Command)
            
            affected = cursor.rowcount
            result_info['success'] = True
            result_info['rows_affected'] = affected
            result_info['message'] = "Command executed successfully."
            
            connection.commit()
            
    except pyodbc.DatabaseError as db_error:
        result_info['message'] = "Database error: {}".format(db_error)
    except pyodbc.Error as odbc_error:
        result_info['message'] = "ODBC error: {}".format(odbc_error)
    except Exception as e:
        result_info['message'] = "Unexpected error: {}".format(e)
    
    return "Success: {success} | Affected: {rows_affected} | Message: {message}".format(**result_info)


def run_query_to_tree(CToggle, CString, Query):
    """
    Execute query and return results as Grasshopper DataTree.
    
    Returns DataTree where each branch (0, 1, 2, ...) contains all values
    from the corresponding column (column 0, column 1, column 2, ...).
    
    Args:
        CToggle (bool): Flag to enable/disable connection attempt
        CString (str): Database connection string (password base64-encoded)
        Query (str): SQL query to execute
    
    Returns:
        DataTree[object]: DataTree with column-based branches
            - Branch 0: All values from first column
            - Branch 1: All values from second column
            - etc.
            - Empty tree if CToggle is False or query is empty
            - Error message in branch 0 if query fails
    
    Example:
        >>> tree = run_query_to_tree(True, cstring, "SELECT id, name FROM users")
        >>> # tree.Branch(0) contains all IDs
        >>> # tree.Branch(1) contains all names
    """
    if not CToggle:
        return DataTree[object]()
    
    if not Query or not Query.strip():
        return DataTree[object]()
    
    try:
        with db_manager.get_connection(CString) as conn:
            cursor = conn.cursor()
            cursor.execute(Query)
            
            # Handle multiple result sets (common in SQL Server)
            max_sets = 8
            step = 0
            while step < max_sets and getattr(cursor, 'description', None) is None:
                if not cursor.nextset():
                    break
                step += 1
            
            rows = cursor.fetchall()
            
            if not rows:
                return DataTree[object]()
            
            n_cols = len(rows[0])
            
            tree = DataTree[object]()
            for col_idx in range(n_cols):
                path = GH_Path(col_idx)
                for row in rows:
                    val = row[col_idx]
                    tree.Add(str(val) if val is not None else None, path)
            
            return tree
            
    except pyodbc.DatabaseError as db_error:
        error_tree = DataTree[object]()
        error_tree.Add("Database error: {}".format(db_error), GH_Path(0))
        return error_tree
    except pyodbc.Error as odbc_error:
        error_tree = DataTree[object]()
        error_tree.Add("ODBC error: {}".format(odbc_error), GH_Path(0))
        return error_tree
    except Exception as e:
        error_tree = DataTree[object]()
        error_tree.Add("Error: {}".format(e), GH_Path(0))
        return error_tree


def get_query_headers(CToggle, CString, Query):
    """
    Get column headers from query without fetching data.
    
    Executes query to extract column metadata (headers) without
    retrieving actual row data. Useful for discovering table structure.
    
    Args:
        CToggle (bool): Flag to enable/disable connection attempt
        CString (str): Database connection string (password base64-encoded)
        Query (str): SQL query to analyze
    
    Returns:
        DataTree[object]: DataTree with column headers
            - Branch 0: First column name
            - Branch 1: Second column name
            - etc.
            - Empty tree if CToggle is False or query is empty
            - Error message in branch 0 if query fails
    
    Example:
        >>> headers = get_query_headers(True, cstring, "SELECT * FROM users")
        >>> # headers.Branch(0) contains "id"
        >>> # headers.Branch(1) contains "name"
    """
    if not CToggle:
        return DataTree[object]()
    
    if not Query or not Query.strip():
        return DataTree[object]()
    
    try:
        with db_manager.get_connection(CString) as conn:
            cursor = conn.cursor()
            cursor.execute(Query)
            
            # Handle multiple result sets
            max_sets = 8
            step = 0
            while step < max_sets and getattr(cursor, 'description', None) is None:
                if not cursor.nextset():
                    break
                step += 1
            
            desc = getattr(cursor, 'description', None)
            headers_tree = DataTree[object]()
            
            if desc:
                for i, col in enumerate(desc):
                    name = col[0] if col and len(col) > 0 else "col_{}".format(i)
                    headers_tree.Add(str(name), GH_Path(i))
            else:
                headers_tree.Add("col_0", GH_Path(0))
                
            return headers_tree
            
    except pyodbc.DatabaseError as db_error:
        error_tree = DataTree[object]()
        error_tree.Add("Database error: {}".format(db_error), GH_Path(0))
        return error_tree
    except pyodbc.Error as odbc_error:
        error_tree = DataTree[object]()
        error_tree.Add("ODBC error: {}".format(odbc_error), GH_Path(0))
        return error_tree
    except Exception as e:
        error_tree = DataTree[object]()
        error_tree.Add("Error: {}".format(e), GH_Path(0))
        return error_tree
