import os
import pathspec
from pathlib import Path
import toml
import argparse
import json
import re
import subprocess

def find_project_root(start_path=None, markers=None):
    if start_path is None:
        start_path = os.getcwd()
    # check if we are at the root of the project.
    if markers is None:
        markers = ['.git', 'pyproject.toml', 'setup.py', 'tests.toml']

    current = os.path.abspath(start_path)
    while True:
        for marker in markers:
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            raise FileNotFoundError("Project root not found.")
        current = parent


def get_excludes_path():
    DEFAULT_FILENAME = "ratchet_excluded.txt"
    root = find_project_root(file)
    return os.path.join(root, DEFAULT_FILENAME)


def get_file_path(file):

    DEFAULT_FILENAME = "tests.toml"

    if not file:
        file = DEFAULT_FILENAME

    if "/" in file:
        return file
    else:
        root = find_project_root(file)
        return os.path.join(root, file)


def get_python_files(directory):
    directory = Path(directory)
    python_files = set([path.absolute() for path in directory.rglob("*.py") if not path.is_symlink()])
    return list(python_files)

def filter_excluded_files(files, excluded_path):
    with open(excluded_path, 'r') as f:
        patterns = f.read().splitlines()

    spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)

    files = [f for f in files if not spec.match_file(f)]

    return files

def evaluate_tests(path, cmd_only, regex_only):

    assert (os.path.isfile(path))

    config = toml.load(path)
    python_tests = config.get("python-tests")
    custom_tests = config.get("custom-tests")
    root = find_project_root()

    files = get_python_files(root)

    EXCLUDED_PATH = "ratchet_excluded.txt"
    excluded_path = os.path.join(root, EXCLUDED_PATH)

    files = filter_excluded_files(files, excluded_path)

    if python_tests and not cmd_only:
        issues = evaluate_python_tests(files, python_tests)
        for test_name, matches in issues.items():
            if matches:
                print(f"\n{test_name} — matched {len(matches)} issue(s):")
                for match in matches:
                    print(f"  → {match['file']}:{match['line']}: {match['content']}")
            else:
                print(f"\n{test_name} — no issues found.")

    if custom_tests and not regex_only:
        issues = evaluate_command_tests(files, custom_tests)
        if issues:
            print("\ncustom-tests — matched issue(s):")
            for file, lines in issues.items():
                print(f"\n{file}:")
                for line in lines:
                    truncated = f"{line[0:80]}..." if len(line) > 80 else line
                    print(f"  → {truncated}")
        else:
            print("\ncustom-tests — no issues found.")

def previous_results():
    path = get_ratchet_path()
    with open(path, 'r') as file:
        data = json.load(file)
    return data
    

def evaluate_python_tests(files, test_str):
    assert len(files) != 0
    assert len(test_str) != 0

    results = {}

    for test_name, rule in test_str.items():
        pattern = re.compile(rule["regex"])
        results[test_name] = []

        for file_path in files:
            with open(file_path, 'r', encoding='utf-8') as f:
                for lineno, line in enumerate(f, 1):
                    if pattern.search(line):
                        results[test_name].append({
                            "file": str(file_path),
                            "line": lineno,
                            "content": line.strip()
                        })

    return results
    
def get_ratchet_path():
    root = find_project_root()
    RATCHET_NAME = "ratchet_values.json"
    ratchet_file_path = os.path.join(root, RATCHET_NAME)
    return ratchet_file_path


# add timeout.
def evaluate_command_tests(files, test_str):
    assert len(test_str) != 0

    issues = {}  # filename -> list of issues

    for test_name, test_dict in test_str.items():
        command_template = test_dict["command"]

        for file in files:
            # Build the full command using pipe: echo file | <command>
            cmd_str = f"echo {file} | {command_template}"

            try:
                # Run the command and capture output
                result = subprocess.run(
                    cmd_str,
                    shell=True,
                    text=True,
                    capture_output=True,
                    timeout=5
                )

                output = result.stdout.strip()
                if output:
                    lines = output.splitlines()
                    if file not in issues:
                        issues[file] = []
                    issues[file].extend(lines)

            except subprocess.TimeoutExpired:
                print(f"Timeout while running test '{test_name}' on {file}")

    return issues

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Python ratchet testing")
    parser.add_argument("-f", "--file",)

    parser.add_argument(
        "-c", "--command-only",
        action="store_true",
        help="Run only custom command-based tests"
    )

    parser.add_argument(
        "-r", "--regex-only",
        action="store_true",
        help="Run only regex-based tests"
    )



    args = parser.parse_args()
    file = args.file

    cmd_mode = args.command_only
    regex_mode = args.regex_only


    test_path = get_file_path(file)

    evaluate_tests(test_path, cmd_mode, regex_mode)
