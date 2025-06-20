import sqlite3
import argparse
from datetime import datetime

class CachingDatabase:

    def __init__(self, path):
        """Initialization method that verifies/creates a DB on disk for caching and does other initalization."""
        self.db_path = path
        self.__create_db__(path)

    def __create_db__(self, path):
        """Internal method for the creation of a caching DB on disk if one has not yet been created."""
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        creation_query = '''
            CREATE TABLE IF NOT EXISTS blames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                line_number INTEGER,
                line_content TEXT,
                timestamp TEXT
            )
        '''
        cursor.execute(creation_query)
        conn.commit()
        cursor.close()


    def create_blame(self, line_content : str, line_number : int, timestamp : datetime, file_name: str):
        """Cache a blame with the line's content, the line number, a timestamp, and the file's name."""
        raise NotImplementedError("Create blame not implemented")

    def update_blame(self, line_content : str, line_number : int, timestamp : datetime, file_name: str):
        """Update the existing blame that has the same line_number and file_name, with a new timestamp and line_content"""
        raise NotImplementedError("Update blame not implemented")

    def clear_cache(self):
        """Clear all cached blames."""
        raise NotImplementedError("Clear cache not implemented")


if __name__ == "__main__":
    """Creates a cache database with the user specified path as the location of the DB on disk."""
    parser = argparse.ArgumentParser(description="Initialize a caching SQLite database.")
    parser.add_argument("path", help="Path to the SQLite database file.")
    args = parser.parse_args()
    db = CachingDatabase(args.path)
