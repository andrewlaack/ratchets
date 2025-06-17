import os
import pathspec
from pathlib import Path
import toml
import argparse
import json
import re

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

def evaluate_tests(path):

    assert (os.path.isfile(path))

    config = toml.load(path)
    python_tests = config.get("python-tests")
    custom_tests = config.get("custom-tests")
    root = find_project_root()

    files = get_python_files(root)

    EXCLUDED_PATH = "ratchet_excluded.txt"
    excluded_path = os.path.join(root, EXCLUDED_PATH)

    files = filter_excluded_files(files, excluded_path)

    if python_tests:
        evaluate_python_tests(python_tests)
    
    if custom_tests:
        evaluate_command_tests(custom_tests)

def previous_results():
    path = get_ratchet_path()
    with open(path, 'r') as file:
        data = json.load(file)
    return data
    
def evaluate_python_tests(test_str):
    assert (len(test_str) != 0)
    
def get_ratchet_path():
    root = find_project_root()
    RATCHET_NAME = "ratchet_values.json"
    ratchet_file_path = os.path.join(root, RATCHET_NAME)
    return ratchet_file_path


def evaluate_command_tests(test_str):
    assert (len(test_str) != 0)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Python ratchet testing")
    parser.add_argument("-f", "--file",)

    args = parser.parse_args()
    file = args.file

    test_path = get_file_path(file)

    evaluate_tests(test_path)
