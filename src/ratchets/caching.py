import sqlite3
import argparse
from datetime import datetime
from typing import Tuple, Optional


# TODO:

# consider if it would be faster to
# store a file handler to the file
# for the life of the db (singleton?)
# as this could speed up lookups
# because a file handler would not need
# to be requested for each method.

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
                timestamp TEXT,
                UNIQUE(file_name, line_number)
            )
        '''

        add_index_query = '''
            CREATE INDEX IF NOT EXISTS idx_blame_file_line
            ON blames(file_name, line_number)
        '''

        cursor.execute(creation_query)
        cursor.execute(add_index_query)

        conn.commit()

        cursor.close()
        conn.close()


    def create_blame(self, line_content : str, line_number : int, timestamp : datetime, file_name: str):
        """Cache a blame with the line's content, the line number, a timestamp, and the file's name."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        create_query = '''
            INSERT INTO blames (file_name, line_number, line_content, timestamp)
            VALUES (?, ?, ?, ?)
        '''

        cursor.execute(create_query, (
            file_name,
            line_number,
            line_content,
            timestamp.isoformat()
        ))

        conn.commit()
        cursor.close()
        conn.close()

    def update_blame(self, line_content : str, line_number : int, timestamp : datetime, file_name: str):
        """Update the existing blame that has the same line_number and file_name, with a new timestamp and line_content"""
        raise NotImplementedError("Update blame not implemented")

    def clear_cache(self):
        """Clear all cached blames."""
        raise NotImplementedError("Clear cache not implemented")

    def get_blame(self, line_number: int, file_name: str) -> Optional[Tuple[str, datetime]]:
        """Lookup the blame for the specified file and line number.

        In cases where no such blame exists, 'None' will be returned.
        This does not guarantee the cached value that is returned
        is valid as an old version of the file could have had
        an issue on this line with different line content. A line
        content lookup should be done on the client side to verify
        the blame is likely up to date. If it is not up to date,
        run another blame and update the record accordingly.
        """
        raise NotImplementedError("Get blame not implemented")



if __name__ == "__main__":
    """Creates a cache database with the user specified path as the location of the DB on disk."""
    parser = argparse.ArgumentParser(description="Initialize a caching SQLite database.")
    parser.add_argument("path", help="Path to the SQLite database file.")
    args = parser.parse_args()
    db = CachingDatabase(args.path)

    db.create_blame(
        "test line content ", 100, datetime.now(), "file_name"
    )

