from ratchets import run_tests
from ratchets import abstracted_tests
import os
import toml
from typing import Dict, Any
import json
import shutil


def test_config():
    test_path = run_tests.get_file_path(None)

    assert os.path.isfile(test_path), "tests.toml not found"

    try:
        issues = run_tests.evaluate_tests(test_path, True, True, None)
        run_tests.update_ratchets(test_path, True, True, None)
    except Exception as e:
        raise Exception(f"Unable to update ratchets using 'tests.toml': {e}")


# TODO:
# add gitignore checks.
# gitignore is handled the same way as
# the excluded file, but should be checked too


def test_exclusion():

    current_file_directory = os.path.dirname(os.path.abspath(__file__))
    excluded_directory = os.path.abspath(
        os.path.join(current_file_directory, "..", "excluded_files")
    )
    test_py_dir = os.path.abspath(
        os.path.join(current_file_directory, "..", "python_files")
    )
    exclusion_path = run_tests.get_excludes_path()
    root = run_tests.find_project_root()
    ignore_path = os.path.join(root, ".gitignore")

    python_files_no_exclusion = run_tests.get_python_files(test_py_dir, None)

    # ensure no side effects in the method
    # since we don't change the path values,
    # ensuring the count reamins the same should suffice

    length_starting = len(python_files_no_exclusion)

    expected_results = {"default_excluded.txt": 6, "no_1.txt": 4, "no_1_or_dir.txt": 3}

    count = 0
    for filename in os.listdir(excluded_directory):
        count += 1
        full_path = os.path.abspath(os.path.join(excluded_directory, filename))
        shutil.copy(full_path, exclusion_path)
        filtered = run_tests.filter_excluded_files(
            python_files_no_exclusion, exclusion_path, ignore_path
        )
        if len(python_files_no_exclusion) != length_starting:
            raise Exception("There is a side effect in filter_excluded_files")

        if not filename in expected_results:
            raise Exception(
                "An additional excluded.txt file was added, but the corresponding expected count was not add to the dict"
            )
        if not expected_results[filename] == len(filtered):
            raise Exception("Filter count differs from expected value")

    if count != len(expected_results):
        raise Exception(
            "There is an entry in the expected_results dictionary that does not correspond with a file tested"
        )


if __name__ == "__main__":
    test_config()
    test_exclusion()
