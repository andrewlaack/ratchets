from ratchets import run_tests
from ratchets import abstracted_tests
import os
import shutil


def test_config():
    test_path = os.path.join(
        run_tests.find_project_root(), "tests/toml_files/default.toml"
    )

    assert os.path.isfile(test_path), "default.toml not found"

    try:
        issues = run_tests.evaluate_tests(test_path, True, True, None)
        run_tests.update_ratchets(
            test_path,
            True,
            True,
            None,
            run_tests.find_project_root() + "/tests/test_files/temp_ratchet1.json",
        )
    except Exception as e:
        assert False, f"Unable to update ratchets using 'tests.toml': {e}"


def test_exclusion():

    current_file_directory = os.path.dirname(os.path.abspath(__file__))
    excluded_directory = os.path.abspath(
        os.path.join(current_file_directory, "..", "excluded_files")
    )
    test_py_dir = os.path.abspath(
        os.path.join(current_file_directory, "..", "python_files")
    )
    exclusion_path = (
        run_tests.find_project_root() + "/tests/exclusion_files/ratchet_excluded.txt"
    )

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

        assert (
            len(python_files_no_exclusion) == length_starting
        ), "There is a side effect in filter_excluded_files"

        assert (
            filename in expected_results
        ), "An additional excluded.txt file was added, but not reflected"

        assert expected_results[filename] == len(
            filtered
        ), "Filter count differs from expected value"

    assert count == len(
        expected_results
    ), "There is an extra entry in the expected_results dictionary"


if __name__ == "__main__":
    test_config()
    test_exclusion()
