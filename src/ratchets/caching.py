import sqlite3
import argparse
from datetime import datetime
from typing import Optional, Dict

# TODO:

# improve performance by adding the ability to bulk create.
# this will stop the commit close cycle which seems to be causing
# quite a bit of latency.

# Benchmarking on Django code base (shell rule of 80 chars max with total of XXX blames evaluated):

# Saving each blame one at a time to SQLite DB
# FIRST RUN: 11m7.030s
# CACHE RUN: 0m2.409s

class CachingDatabase:

    def __init__(self, path: str):
        """Initialization: verify/create DB on disk for caching."""
        self.db_path = path
        self.__create_db__(path)

    def __create_db__(self, path: str):
        """Create table if needed, and add 'author' column if missing."""
        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                line_number INTEGER,
                line_content TEXT,
                timestamp TEXT,
                author TEXT,
                UNIQUE(file_name, line_number)
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_blame_file_line
            ON blames(file_name, line_number)
        ''')


        conn.commit()
        cursor.close()
        conn.close()

    def create_or_update_blame(
        self,
        line_content: str,
        line_number: int,
        timestamp: datetime,
        file_name: str,
        author: str
    ):
        """
        Insert or update a blame:
        if (file_name, line_number) exists, update it; otherwise insert.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        upsert_query = '''
            INSERT INTO blames (file_name, line_number, line_content, timestamp, author)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_name, line_number) DO UPDATE SET
                line_content = excluded.line_content,
                timestamp = excluded.timestamp,
                author = excluded.author
        '''
        cursor.execute(upsert_query, (
            file_name,
            line_number,
            line_content,
            timestamp.isoformat(),
            author
        ))

        conn.commit()
        cursor.close()
        conn.close()

    def get_blame(self, line_number: int, file_name: str) -> Optional[Dict[str, str]]:
        """
        Lookup the blame for the specified file and line number.
        Returns None if not found, else:
        {
            'author': AUTHOR,
            'timestamp': TS (datetime),
            'line_content': content (str)
        }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        select_query = '''
            SELECT author, timestamp, line_content
              FROM blames
             WHERE file_name = ? AND line_number = ?
        '''
        cursor.execute(select_query, (file_name, line_number))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not row:
            return None

        author, ts_str, line_content = row
        try:
            ts = datetime.fromisoformat(ts_str)
        except Exception:
            return None

        return { 'author': str(author), 'timestamp': str(ts), 'line_content': str(line_content)}


if __name__ == "__main__":
    # Simple demo of updated methods
    parser = argparse.ArgumentParser(description="Initialize a caching SQLite database and test blame methods.")
    parser.add_argument("path", help="Path to the SQLite database file.")
    args = parser.parse_args()
    db = CachingDatabase(args.path)

    # Example usage: now must pass author
    example = {
        'content': 'test line content',
        'line_number': 42,
        'timestamp': datetime.now(),
        'file_name': 'some_file.txt',
        'author': 'Alice'
    }
    db.create_or_update_blame(
        example['content'],
        example['line_number'],
        example['timestamp'],
        example['file_name'],
        example['author']
    )

    res = db.get_blame(example['line_number'], example['file_name'])
    if res is None:
        print("No record found")
    else:
        print("Fetched blame:", res)
