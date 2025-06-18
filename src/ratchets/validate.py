import re
import toml
import argparse
from typing import Dict, Any, Optional
from .run_tests import (
    get_file_path,
)

def evaluate_single_regex(regex: str, custom_str: str) -> Optional[re.Match[str]]:
    pattern = re.compile(regex)
    return pattern.search(custom_str)

def check_valid(python_tests: Dict[str, Dict[str, Any]]) -> None:
    for test in python_tests:
        regex: str = python_tests[test]["regex"]
        for validation in python_tests[test]["valid"]:
            for line in validation.splitlines():
                if evaluate_single_regex(regex, line):
                    raise AssertionError(f"Regex: {regex} matched {line}")

def check_invalid(python_tests: Dict[str, Dict[str, Any]]) -> int:
    for test in python_tests:
        regex: str = python_tests[test]["regex"]
        for validation in python_tests[test]["invalid"]:
            found: bool = False
            for line in validation.splitlines():
                if evaluate_single_regex(regex, line):
                    found = True
            if not found:
                raise AssertionError(f"Regex: {regex} not matched in {validation}")
    return 0

def validate(filename : Optional[str]) -> Optional[bool]:
    test_path: str = get_file_path(filename)
    config: Dict[str, Any] = toml.load(test_path)
    python_tests: Optional[Dict[str, Dict[str, Any]]] = config.get("python-tests")

    if python_tests is None:
        print("No python tests found, there is nothing to validate.")
        return True

    check_valid(python_tests)
    check_invalid(python_tests)
    return True


    print(f"All expected regex invalid/valid samples are correct for:\n{test_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Python ratchet testing")
    parser.add_argument("-f", "--file")
    args = parser.parse_args()
    file: Optional[str] = args.file
    validate(file)

