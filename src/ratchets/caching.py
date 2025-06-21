import sqlite3
import argparse
from datetime import datetime
from typing import Optional, Dict, List


class BlameRecord:
    def __init__(
        self,
        line_content: str,
        line_number: int,
        timestamp: datetime,
        file_name: str,
        author: str,
    ):
        """Creates a record based on required fields for compatability with blame cache."""
        self.line_content = line_content
        self.line_number = line_number
        self.timestamp = timestamp
        self.file_name = file_name
        self.author = author


class CachingDatabase:

    def __init__(self, path: str):
        """Initialization: verify/create DB on disk for caching."""
        self.db_path = path
        self.__create_db__(path)

    def __create_db__(self, path: str):
        """Create table if needed, and add 'author' column if missing."""
        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS blames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                line_number INTEGER,
                line_content TEXT,
                timestamp TEXT,
                author TEXT,
                UNIQUE(file_name, line_number)
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_blame_file_line
            ON blames(file_name, line_number)
        """
        )

        conn.commit()
        cursor.close()
        conn.close()

    def create_or_update_blames(self, blames: List[BlameRecord]):
        """
        Insert or update a list of blames:
        if (file_name, line_number) exists, update it; otherwise insert.
        """

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA journal_mode = OFF")
        cursor.execute("PRAGMA synchronous = OFF")

        upsert_query = """
            INSERT INTO blames (file_name, line_number, line_content, timestamp, author)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_name, line_number) DO UPDATE SET
                line_content = excluded.line_content,
                timestamp = excluded.timestamp,
                author = excluded.author
        """

        cursor.executemany(
            upsert_query,
            [
                (
                    blame.file_name,
                    blame.line_number,
                    blame.line_content,
                    blame.timestamp.isoformat(),
                    blame.author,
                )
                for blame in blames
            ],
        )

        conn.commit()
        cursor.close()
        conn.close()

    def create_or_update_blame(self, blame: BlameRecord):
        """
        Insert or update a blame:
        if (file_name, line_number) exists, update it; otherwise insert.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        upsert_query = """
            INSERT INTO blames (file_name, line_number, line_content, timestamp, author)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_name, line_number) DO UPDATE SET
                line_content = excluded.line_content,
                timestamp = excluded.timestamp,
                author = excluded.author
        """
        cursor.execute(
            upsert_query,
            (
                blame.file_name,
                blame.line_number,
                blame.line_content,
                blame.timestamp.isoformat(),
                blame.author,
            ),
        )

        conn.commit()
        cursor.close()
        conn.close()

    def get_blame(self, line_number: int, file_name: str) -> Optional[BlameRecord]:
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

        select_query = """
            SELECT author, timestamp, line_content
              FROM blames
             WHERE file_name = ? AND line_number = ?
        """
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

        blame = BlameRecord(line_content, line_number, ts, file_name, author)

        return blame

    def clear_cache(self) -> None:
        """Clear the local blame caching DB."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blames")
        conn.commit()
        cursor.close()
        conn.close()
