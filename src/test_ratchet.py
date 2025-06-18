import os
import json
import pytest
import toml
from pathlib import Path
from run_tests import (
    evaluate_python_tests,
    evaluate_command_tests,
    filter_excluded_files,
    find_project_root,
    get_python_files,
    get_ratchet_path
)

ROOT = find_project_root()
TOML_PATH = Path(ROOT) / "tests.toml"
CONFIG = toml.load(TOML_PATH)

PYTHON_TESTS = CONFIG.get("python-tests", {})
COMMAND_TESTS = CONFIG.get("custom-tests", {})

def load_baseline_counts():
    """
    Load previous counts from ratchet_values.json.
    Return a dict mapping test_name -> count. If file missing or malformed, return empty dict.
    """
    try:
        ratchet_path = get_ratchet_path()
        if os.path.isfile(ratchet_path):
            with open(ratchet_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Ensure values are ints
                    return {k: int(v) for k, v in data.items()}
    except Exception:
        pass
    return {}

BASELINE_COUNTS = load_baseline_counts()

@pytest.mark.parametrize("test_name,rule", PYTHON_TESTS.items())
def test_python_regex_rule(test_name, rule):
    # Prepare file list
    root = find_project_root()
    files = get_python_files(root)
    EXCLUDED_PATH = "ratchet_excluded.txt"
    excluded_path = os.path.join(root, EXCLUDED_PATH)
    ignore_path = os.path.join(root, ".gitignore")
    files = filter_excluded_files(files, excluded_path, ignore_path)

    # Evaluate current results
    results = evaluate_python_tests(files, {test_name: rule})
    current_matches = results.get(test_name, [])
    current_count = len(current_matches)

    # Baseline
    baseline_count = BASELINE_COUNTS.get(test_name, 0)

    # If increased, fail.
    assert current_count <= baseline_count, (
        f"Regex violations for '{test_name}' increased: "
        f"baseline={baseline_count}, current={current_count}\n"
        + (
            "\n".join(
                f"{r['file']}:{r['line']} — {r['content']}"
                for r in current_matches
            )
          if current_count > 0 else ""
        )
    )

@pytest.mark.parametrize("test_name,test_dict", COMMAND_TESTS.items())
def test_custom_command_rule(test_name, test_dict):
    # Prepare file list
    root = find_project_root()
    files = get_python_files(root)
    EXCLUDED_PATH = "ratchet_excluded.txt"
    excluded_path = os.path.join(root, EXCLUDED_PATH)
    ignore_path = os.path.join(root, ".gitignore")
    files = filter_excluded_files(files, excluded_path, ignore_path)

    # Evaluate current results
    results = evaluate_command_tests(files, {test_name: test_dict})
    current_matches = results.get(test_name, [])
    current_count = len(current_matches)

    # Baseline
    baseline_count = BASELINE_COUNTS.get(test_name, 0)

    # If increased, fail.
    assert current_count <= baseline_count, (
        f"Command violations for '{test_name}' increased: "
        f"baseline={baseline_count}, current={current_count}\n"
        + (
            "\n".join(
                f"{r['file']} — {r['content']}"
                for r in current_matches
            )
          if current_count > 0 else ""
        )
    )
