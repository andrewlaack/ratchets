import os
import json
import toml
from pathlib import Path
from typing import Dict, Any, List

from .run_tests import (
    evaluate_regex_tests,
    evaluate_shell_tests,
    filter_excluded_files,
    find_project_root,
    get_python_files,
    get_ratchet_path,
)


def get_root() -> str:
    """Return the project root directory."""
    return find_project_root()


def get_config() -> Dict[str, Any]:
    """Load and return the tests.toml configuration."""
    root = get_root()
    toml_path = Path(root) / "tests.toml"
    try:
        return toml.load(toml_path)
    except Exception:
        return {}


def get_regex_tests() -> Dict[str, Any]:
    """Extract and return the 'ratchet.regex' section from config."""
    config = get_config()
    python_tests = config.get("ratchet", {}).get("regex")
    return python_tests or {}


def get_shell_tests() -> Dict[str, Any]:
    """Extract and return the 'ratchet.shell' section from config."""
    config = get_config()
    shell_tests = config.get("ratchet", {}).get("shell")
    return shell_tests or {}


def load_baseline_counts() -> Dict[str, int]:
    """Load baseline counts from ratchet path, returning a dict of test names and counts."""
    try:
        ratchet_path: str = get_ratchet_path()
        if os.path.isfile(ratchet_path):
            with open(ratchet_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {k: int(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def get_baseline_counts() -> Dict[str, int]:
    """Return baseline counts"""
    return load_baseline_counts()


def get_filtered_files() -> List[Path]:
    """Retrieve all Python files under the project, filtering excluded paths."""
    root = get_root()
    files: List[Path] = get_python_files(root, None)
    excluded_path: str = os.path.join(root, "ratchet_excluded.txt")
    ignore_path: str = os.path.join(root, ".gitignore")

    try:
        return filter_excluded_files(files, excluded_path, ignore_path)
    except Exception:
        return files


def get_python_test_matches(
    test_name: str, rule: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Run a regex test for a single rule and return matches."""
    files = get_filtered_files()
    results: Dict[str, List[Dict[str, Any]]] = evaluate_regex_tests(
        files, {test_name: rule}
    )
    return results.get(test_name, [])


def get_shell_test_matches(
    test_name: str, test_dict: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Run a shell test for a single rule and return matches."""
    files = get_filtered_files()
    results: Dict[str, List[Dict[str, Any]]] = evaluate_shell_tests(
        files, {test_name: test_dict}
    )
    return results.get(test_name, [])


def check_regex_rule(test_name: str, rule: Dict[str, Any]) -> None:
    """Check if a single regex rule has been violated by increasing infraction count."""
    assert test_name is not None
    assert rule is not None

    matches = get_python_test_matches(test_name, rule)
    current_count = len(matches)
    baseline_counts = get_baseline_counts()
    baseline_count = baseline_counts.get(test_name, 0)
    if current_count > baseline_count:
        description = rule.get('description')
        if description is None:
            description = ""

        raise Exception(
            f"'{test_name}' increased from {baseline_count} to {current_count}"
            +  ". " + str(description)
        )


def check_shell_rule(test_name: str, test_dict: Dict[str, Any]) -> None:
    """Check if a single shell rule has been violated by increasing infraction count."""
    assert test_name is not None
    assert test_dict is not None

    matches = get_shell_test_matches(test_name, test_dict)
    current_count = len(matches)
    baseline_counts = get_baseline_counts()
    baseline_count = baseline_counts.get(test_name, 0)
    if current_count > baseline_count:
        description = test_dict.get('description')
        if description is None:
            description = ""
        raise Exception(
            f"'{test_name}' increased from {baseline_count} to {current_count}"
            + ". " + str(description)
        )
