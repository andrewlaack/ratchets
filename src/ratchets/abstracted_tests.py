import os
import json
import toml
from pathlib import Path
from typing import Dict, Any, List

from .run_tests import (
    evaluate_python_tests,
    evaluate_command_tests,
    filter_excluded_files,
    find_project_root,
    get_python_files,
    get_ratchet_path,
)


def get_root() -> str:
    """Return the project root directory."""
    return find_project_root()


def get_config() -> Dict[str, Any]:
    """Load and return the tests.toml configuration as a dict."""
    root = get_root()
    toml_path = Path(root) / "tests.toml"
    try:
        return toml.load(toml_path)
    except Exception:
        return {}


def get_python_tests() -> Dict[str, Any]:
    """Extract and return the 'python-tests' section from config."""
    config = get_config()
    return config.get("python-tests", {}) or {}


def get_command_tests() -> Dict[str, Any]:
    """Extract and return the 'custom-tests' section from config."""
    config = get_config()
    return config.get("custom-tests", {}) or {}


def load_baseline_counts() -> Dict[str, int]:
    """Load baseline counts from ratchet path, returning a dict of test_name to count."""
    try:
        ratchet_path: str = get_ratchet_path()
        if os.path.isfile(ratchet_path):
            with open(ratchet_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {k: int(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def get_baseline_counts() -> Dict[str, int]:
    """Return baseline counts, caching on first call."""
    return load_baseline_counts()


def get_filtered_files() -> List[Path]:
    """Retrieve all Python files under the project, filtering excluded paths."""
    root = get_root()
    files: List[Path] = get_python_files(root)
    excluded_path: str = os.path.join(root, "ratchet_excluded.txt")
    ignore_path: str = os.path.join(root, ".gitignore")
    try:
        return filter_excluded_files(files, excluded_path, ignore_path)
    except Exception:
        return files


def get_python_test_matches(test_name: str, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run the Python regex test for a single rule and return matches."""
    files = get_filtered_files()
    results: Dict[str, List[Dict[str, Any]]] = evaluate_python_tests(files, {test_name: rule})
    return results.get(test_name, [])


def get_command_test_matches(test_name: str, test_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run the custom command test for a single rule and return matches."""
    files = get_filtered_files()
    results: Dict[str, List[Dict[str, Any]]] = evaluate_command_tests(files, {test_name: test_dict})
    return results.get(test_name, [])


def check_python_rule(test_name: str, rule: Dict[str, Any]) -> None:
    
    assert (test_name is not None)
    assert (rule is not None)

    matches = get_python_test_matches(test_name, rule)
    current_count = len(matches)
    baseline_counts = get_baseline_counts()
    baseline_count = baseline_counts.get(test_name, 0)
    if current_count > baseline_count:
        details = "\n".join(
            f"{r.get('file')}:{r.get('line')} — {r.get('content')}" for r in matches
        )
        raise AssertionError(
            f"Regex violations for '{test_name}' increased: baseline={baseline_count}, current={current_count}\n" + details
        )


def check_command_rule(test_name: str, test_dict: Dict[str, Any]) -> None:
    
    assert (test_name is not None)
    assert (test_dict is not None)

    matches = get_command_test_matches(test_name, test_dict)
    current_count = len(matches)
    baseline_counts = get_baseline_counts()
    baseline_count = baseline_counts.get(test_name, 0)
    if current_count > baseline_count:
        details = "\n".join(
            f"{r.get('file')} — {r.get('content')}" for r in matches
        )
        raise AssertionError(
            f"Command violations for '{test_name}' increased: baseline={baseline_count}, current={current_count}\n" + details
        )
