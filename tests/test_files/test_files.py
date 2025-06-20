from ratchets import run_tests
from ratchets import abstracted_tests
import os
import json


def test_files():
    """Tests the functionallity of .toml and file specification."""

    # directory: Union[str, Path], paths: Optional[List[str]]
    # ) -> List[Path]:

    proj_root = run_tests.find_project_root()

    file1_path = [os.path.join(proj_root, "tests/file_spec_files/spec_file_1.py")]
    file2_path = [os.path.join(proj_root, "tests/file_spec_files/spec_file_2.py")]

    filtered1_file = str(abstracted_tests.get_python_files(proj_root, file1_path)[0])
    filtered2_file = str(abstracted_tests.get_python_files(proj_root, file2_path)[0])

    current_file_directory = os.path.dirname(os.path.abspath(__file__))
    toml_file_directory = os.path.abspath(
        os.path.join(current_file_directory, "..", "toml_files")
    )
    toml_file = os.path.join(toml_file_directory, "default.toml")

    exceptions1 = run_tests.evaluate_tests(
        toml_file, False, False, [filtered1_file], True
    )

    exceptions2 = run_tests.evaluate_tests(
        toml_file, False, False, [filtered2_file], True
    )

    json1 = json.loads(run_tests.results_to_json(exceptions1))
    json2 = json.loads(run_tests.results_to_json(exceptions2))

    exception1_sum = 0
    for key in json1:
        exception1_sum += json1[key]

    exception2_sum = 0
    for key in json2:
        exception2_sum += json2[key]

    if exception2_sum != 8:
        raise Exception(f"Incorrect number of infractions counted for {filtered2_file}")
    if exception1_sum != 6:
        raise Exception(f"Incorrect number of infractions counted for {filtered1_file}")


if __name__ == "__main__":
    """Invoke all tests in the file when called directly."""
    test_files()
