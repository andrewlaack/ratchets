import pytest
import toml
from pathlib import Path
from run_tests import (
    evaluate_python_tests,
    evaluate_command_tests,
    get_python_files,
    find_project_root
)

# Load the TOML config once
ROOT = find_project_root()
TOML_PATH = Path(ROOT) / "tests.toml"
CONFIG = toml.load(TOML_PATH)

PYTHON_TESTS = CONFIG.get("python-tests", {})
COMMAND_TESTS = CONFIG.get("custom-tests", {})


@pytest.mark.parametrize("test_name,rule", PYTHON_TESTS.items())
def test_python_regex_rule(test_name, rule):
    """
    Fails if any regex match is found in the project files.
    """
    files = get_python_files(ROOT)
    results = evaluate_python_tests(files, {test_name: rule})
    assert not results[test_name], (
        f"Regex violations found for '{test_name}':\n" +
        "\n".join(f"{r['file']}:{r['line']} — {r['content']}" for r in results[test_name])
    )


@pytest.mark.parametrize("test_name,test_dict", COMMAND_TESTS.items())
def test_custom_command_rule(test_name, test_dict):
    """
    Fails if custom shell command detects output in any file.
    """
    files = get_python_files(ROOT)
    results = evaluate_command_tests(files, {test_name: test_dict})
    assert not results[test_name], (
        f"Command violations found for '{test_name}':\n" +
        "\n".join(f"{r['file']} — {r['content']}" for r in results[test_name])
    )
