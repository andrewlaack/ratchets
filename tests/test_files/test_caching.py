from ratchets.caching import CachingDatabase, BlameRecord
from ratchets.abstracted_tests import find_project_root
import os
from datetime import datetime

CACHING_FILENAME = ".ratchet_blame.db"


def test_create_new_db():
    """Ensure DB creation when one does not exist works as expected."""
    repo_root = find_project_root()
    db_path = os.path.join(str(repo_root), CACHING_FILENAME)
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass
    db = CachingDatabase(db_path)


def test_create_multi_connections():
    """Ensure multiple DB connections can be created concurrently."""
    for i in range(0, 10):
        repo_root = find_project_root()
        db_path = os.path.join(str(repo_root), CACHING_FILENAME)
        os.remove(db_path)
        db = CachingDatabase(db_path)


def test_record_updating():
    """Ensure records are updated correctly when line numbers and file names match."""

    repo_root = find_project_root()
    db_path = os.path.join(str(repo_root), CACHING_FILENAME)
    if os.path.exists(db_path):
        os.remove(db_path)
    db = CachingDatabase(db_path)

    file_name = "example.py"
    line_number = 42

    # create record
    record1 = BlameRecord(
        line_content="print('Hello, world!')",
        line_number=line_number,
        timestamp=datetime(2020, 1, 1, 12, 0, 0),
        file_name=file_name,
        author="Author1",
    )
    db.create_or_update_blame(record1)

    # update with new author/timestamp/content
    record2 = BlameRecord(
        line_content="print('Updated!')",
        line_number=line_number,
        timestamp=datetime(2021, 1, 1, 12, 0, 0),
        file_name=file_name,
        author="Author2",
    )
    db.create_or_update_blame(record2)

    updated = db.get_blame(line_number, file_name)

    assert updated is not None, "We inserted this record; it should not be 'None'"

    assert updated.author == "Author2", "Single-record update failed"
    assert updated.line_content == "print('Updated!')"

    # test batch updating
    record3 = BlameRecord(
        line_content="print('Batch update!')",
        line_number=line_number,
        timestamp=datetime(2022, 1, 1, 12, 0, 0),
        file_name=file_name,
        author="Author3",
    )
    db.create_or_update_blames([record3])

    updated = db.get_blame(line_number, file_name)

    assert updated is not None, "We inserted this record; it should not be 'None'"
    assert updated.author == "Author3", "Batch-record update failed"
    assert updated.line_content == "print('Batch update!')"

    print("test_record_updating passed")


if __name__ == "__main__":
    test_create_new_db()
    test_create_multi_connections()
    test_record_updating()
