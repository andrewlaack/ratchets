from ratchets import run_tests
from ratchets import abstracted_tests
import os
import toml
from typing import Dict, Any
import json

# verify code still runs as expected even
# if only shell or regex sections are defined

# also, ensure sufficiently informative message is shown when
# invalid toml is used.

# ensure environment is configured correctly for other tests to run.
# this creates a ratchet_excluded.txt file,
# creates the output json, and verifies there is a default tests.toml file


def test_config():
    test_path = run_tests.find_project_root() + "/tests/toml_files/default.toml"

    assert os.path.isfile(test_path), "default.toml not found"

    try:
        issues = run_tests.evaluate_tests(test_path, True, True, None)
        run_tests.update_ratchets(test_path, True, True, None, run_tests.find_project_root() + "/tests/test_files/temp_ratchet1.json")
    except Exception as e:
        assert False, f"Unable to update ratchets using 'tests.toml': {e}"



def test_formatting():
    current_file_directory = os.path.dirname(os.path.abspath(__file__))
    toml_file_directory = os.path.abspath(
        os.path.join(current_file_directory, "..", "toml_files")
    )

    for filename in os.listdir(toml_file_directory):
        if filename == "invalid.toml":
            try:
                full_path = os.path.abspath(os.path.join(toml_file_directory, filename))
                run_tests.evaluate_tests(full_path, True, True, None)
            except Exception as e:
                assert isinstance(
                    e, toml.TomlDecodeError
                ), f"Expected TomlDecodeError, got {type(e)}: {e}"
            else:
                assert False, "Expected error to be thrown for invalid toml file."

        else:
            full_path = os.path.abspath(os.path.join(toml_file_directory, filename))

            # there is a directory in there
            if os.path.isfile(full_path):
                run_tests.evaluate_tests(full_path, True, True, None)

        full_path = os.path.abspath(os.path.join(toml_file_directory, filename))


# ensure updated values match subsequent runs.
def verify_updating():
    test_path = run_tests.find_project_root() + "/tests/toml_files/default.toml"

    run_tests.update_ratchets(test_path, True, True, None)

    # if one is false then the results are guaranteed
    # to be either the same or lower.

    issues = run_tests.evaluate_tests(test_path, True, True, None)
    current_json: Dict[str, Any] = json.loads(run_tests.results_to_json(issues))
    previous_json: Dict[str, Any] = run_tests.load_ratchet_results()

    assert (
        current_json == previous_json
    ), "JSON should be identical when running evals and updating ratchets."


# test how things behave when ratchet_values.json does not exist
def test_ratchet_excluded_missing():

    ratchet_path = abstracted_tests.get_ratchet_path()

    if os.path.isfile(ratchet_path):
        try:
            os.remove(ratchet_path)
        except Exception as e:
            assert False, "Unable to delete ratchet_values.json"

    test_path = run_tests.find_project_root() + "/tests/toml_files/default.toml"

    try:
        previous = run_tests.load_ratchet_results()
    except Exception:
        assert (
            False
        ), "If ratchet_values.json does not exist, we don't throw, assume all 0's"

    issues = run_tests.evaluate_tests(test_path, True, True, None)

    # writes back json file
    run_tests.update_ratchets(test_path, True, True, None)

    return

# test when there are additional values,
# less values, no values (in current).


def test_ratchet_values_differ():

    # ensure clean start
    test_config()

    current_file_directory = os.path.dirname(os.path.abspath(__file__))
    toml_file_directory = os.path.abspath(
        os.path.join(current_file_directory, "..", "toml_files/different")
    )

    for filename in os.listdir(toml_file_directory):
        full_path = os.path.abspath(os.path.join(toml_file_directory, filename))
        run_tests.evaluate_tests(full_path, True, True, None)
        full_path = os.path.abspath(os.path.join(toml_file_directory, filename))

    return


if __name__ == "__main__":
    test_config()
    test_formatting()
    test_ratchet_excluded_missing()
    test_ratchet_values_differ()
