import os
import threading
import pathspec
from datetime import datetime
from pathlib import Path
import toml
import argparse
import json
import re
import subprocess
from typing import Optional, List, Dict, Tuple, Union, Any

EXCLUDED_FILENAME = "ratchet_excluded.txt"
IGNORE_FILENAME = ".gitignore"
RATCHET_FILENAME = "ratchet_values.json"
TEST_FILENAME = "tests.toml"


def print_diff(current_json: Dict[str, int], previous_json: Dict[str, int]) -> None:
    """Print formatted json and differences."""
    all_keys = set(current_json.keys()) | set(previous_json.keys())
    diff_count = 0

    for key in sorted(all_keys):
        current_value = current_json.get(key, 0)
        previous_value = previous_json.get(key, 0)
        if current_value != previous_value:
            diff_count += 1
            diff = current_value - previous_value
            sign = "+" if diff > 0 else "-"
            print(f"  {key}: {previous_value} -> {current_value} ({sign}{abs(diff)})")

    if diff_count == 0:
        print("There are no differences.")


def find_project_root(
    start_path: Optional[str] = None, markers: Optional[List[str]] = None
) -> str:
    """Return the root of the current project starting from start_path or cwd."""
    if start_path is None:
        start_path = os.getcwd()

    if markers is None:
        markers = [".git", "pyproject.toml", "setup.py", "tests.toml"]

    current = os.path.abspath(start_path)

    while True:
        for marker in markers:
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            raise FileNotFoundError("Project root not found.")
        current = parent


def get_excludes_path() -> str:
    """Get the path for the 'ratchet_excluded.txt' file."""
    root = find_project_root(None)
    return os.path.join(root, EXCLUDED_FILENAME)


def get_file_path(file: Optional[str]) -> str:
    """Get the path, as a string, for the 'tests.toml' file or return a file path with a matching name to 'file'."""
    if file is None or len(file) == 0:
        file = TEST_FILENAME
        root = find_project_root(file)
        return str(os.path.join(root, file))
    return file


def get_python_files(
    directory: Union[str, Path], paths: Optional[List[str]]
) -> List[Path]:
    """Return a list of paths for python files in the specified directory."""

    if paths:
        path_paths = [Path(x) for x in paths]
        return path_paths

    directory = Path(directory)
    python_files = set(
        [path.absolute() for path in directory.rglob("*.py") if not path.is_symlink()]
    )
    return list(python_files)


def filter_excluded_files(
    files: List[Path], excluded_path: str, ignore_path: str
) -> List[Path]:
    """Returns a new list of file paths that consists of all 'files' paths not excluded in the 'excluded_path' or 'ignore_path'."""
    patterns = []
    if os.path.isfile(excluded_path):
        with open(excluded_path, "r") as f:
            patterns += f.read().splitlines()

    if os.path.isfile(ignore_path):
        with open(ignore_path, "r") as f:
            patterns += f.read().splitlines()

    spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    files = [f for f in files if not spec.match_file(f)]
    return files


def evaluate_tests(
    path: str,
    cmd_only: bool,
    regex_only: bool,
    paths: Optional[List[str]],
    override_filter: bool = False,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    """Runs all requested tests based on the 'path' .toml file."""
    assert os.path.isfile(path)

    config = toml.load(path)

    regex_tests = config.get("ratchet", {}).get("regex")
    shell_tests = config.get("ratchet", {}).get("shell")

    root = find_project_root()
    files = get_python_files(root, paths)

    excluded_path = os.path.join(root, EXCLUDED_FILENAME)
    ignore_path = os.path.join(root, IGNORE_FILENAME)

    if not override_filter:
        files = filter_excluded_files(files, excluded_path, ignore_path)

    regex_issues: Dict[str, List[Dict[str, Any]]] = {}
    shell_issues: Dict[str, List[Dict[str, Any]]] = {}

    if regex_tests and not cmd_only:
        regex_issues = evaluate_regex_tests(files, regex_tests)
    if shell_tests and not regex_only:
        shell_issues = evaluate_shell_tests(files, shell_tests)
    return regex_issues, shell_issues


def print_issues(issues: Dict[str, List[Dict[str, Any]]]) -> None:
    """Print the 'issues' dict in a human readable way."""
    for test_name, matches in issues.items():
        if matches:
            print(f"\n{test_name} — matched {len(matches)} issue(s):")
            for match in matches:
                file_path = match["file"]
                line = match.get("line")
                content = match["content"]
                truncated = content if len(content) <= 50 else content[:50] + "..."
                if line is not None:
                    print(f"  -> {file_path}:{line}: {truncated}")
                else:
                    print(f"  -> {file_path}: {truncated}")
        else:
            print(f"\n{test_name} — no issues found.")


def load_ratchet_results() -> Dict[str, Any]:
    """Load and return current ratchet values.."""
    path = get_ratchet_path()

    if not os.path.isfile(path):
        return {}

    with open(path, "r") as file:
        data = json.load(file)

    return dict(data)


def evaluate_regex_tests(
    files: List[Path], test_str: Dict[str, Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """Evaluate a list of regex tests in parallel with one thread per test."""
    if len(files) == 0:
        raise Exception("No files were passed in to be evaluated.")
    if len(test_str) == 0:
        raise Exception("No regex tests were passed in to be evaluated.")

    results: Dict[str, List[Dict[str, Any]]] = {}
    threads = []
    results_lock = threading.Lock()

    def eval_thread(test_name: str, rule: Dict[str, Any]):
        pattern = re.compile(rule["regex"])
        matches = []

        for file_path in files:
            with open(file_path, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if pattern.search(line):
                        matches.append(
                            {
                                "file": str(file_path),
                                "line": lineno,
                                "content": line.strip(),
                            }
                        )
        with results_lock:
            results[test_name] = matches

    for test_name, rule in test_str.items():
        thread = threading.Thread(target=eval_thread, args=(test_name, rule))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    return results


def get_ratchet_path() -> str:
    """Get the path for the ratchet values file on disk."""
    root = find_project_root()
    ratchet_file_path = os.path.join(root, RATCHET_FILENAME)
    return ratchet_file_path


def evaluate_shell_tests(
    files: List[Path], test_str: Dict[str, Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """Evaluate all shell tests in parallel across each file."""
    if len(test_str) == 0:
        raise Exception("No shell tests passed to evaluation method.")
    if len(files) == 0:
        raise Exception("No files passed to evaluation method.")

    results: Dict[str, List[Dict[str, Any]]] = {test_name: [] for test_name in test_str}
    lock = threading.Lock()

    # we track each line number
    # for duplicates, popping them
    # as they are used, if they are
    # used.

    file_lines_map: Dict[str, Dict[str, List[int]]] = {}

    # TODO:
    # Parallelize map creation; this is heavily I/O bound.
    # Also, check if this is the best approach. Would it
    # just be better to run in O(n) given smaller coefficients?

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                file_map: Dict[str, List[int]] = {}
                for idx, line in enumerate(lines):
                    normalized = line.rstrip("\n")
                    file_map.setdefault(normalized, []).append(idx + 1)
                file_lines_map[str(file_path)] = file_map
        except Exception as e:
            raise Exception(f"Error reading {file_path}: {e}")

    def worker(test_name: str, shell_template: str, file_path: Path):
        """Evaluate an individual shell test for a given file."""
        file_str = str(file_path)
        cmd_str = f"echo {file_str} | {shell_template}"

        try:
            result = subprocess.run(
                cmd_str, shell=True, text=True, capture_output=True, timeout=5
            )

            output = result.stdout.strip()

            if output:
                lines = output.splitlines()

                with lock:
                    for line in lines:

                        content = line.rstrip("\n")
                        line_numbers = file_lines_map[file_str].get(content, [])

                        # assume we found the last line this happened,
                        # remove it, and repeat for each infraction of this line.
                        # this can be wrong, but it is impossible to
                        # solve the ambiguity of multiple lines matching,
                        # but not causing infractions, which can happen
                        # when shell commands are defined to consider multiple lines,
                        # as can be the case with ast and such.

                        if line_numbers:
                            ln = line_numbers[0]
                            line_numbers.pop()
                            results[test_name].append(
                                {
                                    "file": file_str,
                                    "line": ln,
                                    "content": content,
                                }
                            )

        except subprocess.TimeoutExpired:
            raise Exception(f"Timeout while running test '{test_name}' on {file_path}")

    threads = []

    for test_name, test_dict in test_str.items():
        shell_template = test_dict["command"]
        for file_path in files:
            t = threading.Thread(
                target=worker, args=(test_name, shell_template, file_path)
            )
            t.start()
            threads.append(t)

    for t in threads:
        t.join()

    return results


def results_to_json(
    results: Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]],
) -> str:
    """Convert test results to a standard JSON formatted string."""
    test_issues, shell_issues = results
    counts: Dict[str, int] = {}

    for name, matches in test_issues.items():
        counts[name] = len(matches)

    for name, matches in shell_issues.items():
        counts[name] = counts.get(name, 0) + len(matches)

    return json.dumps(counts, indent=2, sort_keys=True)


def update_ratchets(
    test_path: str, cmd_mode: bool, regex_mode: bool, paths: Optional[List[str]]
) -> None:
    """Update the current ratchets based on the outcome of the tests defined in 'test_path'."""
    results = evaluate_tests(test_path, cmd_mode, regex_mode, paths)
    results_json = results_to_json(results)
    path = get_ratchet_path()
    with open(path, "w") as file:
        file.writelines(results_json)


def print_issues_with_blames(
    results: Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]],
    max_count: int,
) -> None:
    """For the results in 'results', get blame results for each result and then print the results in a human readable format."""
    enriched_test_issues, enriched_shell_issues = add_blames(results)

    def _parse_time(ts: Optional[str]) -> datetime:
        """Internal method used to convert formatted strings to datetimes."""
        if not ts:
            return datetime.max
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return datetime.max

    def _print_section(
        section_name: str, issues_dict: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """Internal method used to print the results from an individual test."""
        for test_name, matches in issues_dict.items():
            if matches:
                sorted_matches = sorted(
                    matches,
                    key=lambda m: _parse_time(m.get("blame_time")),
                    reverse=True,
                )
                print()
                print(
                    f"{section_name} — {test_name} ({len(sorted_matches)} issue{'s' if len(sorted_matches) != 1 else ''}):"
                )
                print()
                count = 0

                for match in sorted_matches:
                    count += 1

                    if count > max_count:
                        break

                    file_path = match.get("file", "<unknown>")
                    line_no = match.get("line")
                    content = match.get("content", "").strip()
                    truncated = content if len(content) <= 80 else content[:80] + "..."
                    author = match.get("blame_author") or "Unknown"
                    ts = match.get("blame_time") or "Unknown"

                    if line_no is not None:
                        print(f"  -> {file_path}:{line_no}  by {author} at {ts}")
                        print(f"       {truncated}")
                    else:
                        print(
                            f"  -> {file_path}  file last updated by {author} at {ts}"
                        )
                        print(f"       {truncated}")
            else:
                print(f"\n{section_name} — {test_name}: no issues found.")

    _print_section("Regex Test", enriched_test_issues)
    _print_section("Shell Test", enriched_shell_issues)


def add_blames(
    results: Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    """Add blame information to each result in the 'results' tuple."""
    test_issues, shell_issues = results

    try:
        repo_root: Optional[str] = find_project_root()
    except Exception:
        repo_root = None

    def get_blame_for_line(
        file_path: str, line_no: Optional[int]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Internal method for getting the blame information of a specific LoC."""
        if repo_root is None:
            return None, None
        cmd = ["git", "blame", "-L", f"{line_no},{line_no}", "--porcelain", file_path]
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, cwd=repo_root, timeout=5
            )
            if res.returncode != 0:
                return None, None

            author: Optional[str] = None
            author_time: Optional[str] = None

            for l in res.stdout.splitlines():
                if l.startswith("author "):
                    author = l[len("author ") :].strip()
                elif l.startswith("author-time "):
                    try:
                        ts = int(l[len("author-time ") :].strip())
                        author_time = datetime.fromtimestamp(ts).isoformat()
                    except Exception:
                        author_time = None
                if author is not None and author_time is not None:
                    break
            return author, author_time
        except Exception:
            return None, None

    def get_last_commit_for_file(file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Internal method to get the most recent commit's information for a file."""
        if repo_root is None:
            return None, None
        cmd = ["git", "log", "-1", "--format=%an;%at", "--", file_path]
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, cwd=repo_root, timeout=5
            )
            if res.returncode != 0 or not res.stdout.strip():
                return None, None
            out = res.stdout.strip()
            parts = out.split(";", 1)
            if len(parts) != 2:
                return None, None
            author = parts[0].strip()
            try:
                ts = int(parts[1].strip())
                author_time = datetime.fromtimestamp(ts).isoformat()
            except Exception:
                author_time = None
            return author, author_time
        except Exception:
            return None, None

    for issues in (test_issues, shell_issues):
        for test_name, matches in issues.items():
            for match in matches:
                file_path = match.get("file")
                line_no = match.get("line")
                if not file_path:
                    continue
                if line_no is not None:
                    author, author_time = get_blame_for_line(file_path, line_no)
                else:
                    author, author_time = get_last_commit_for_file(file_path)
                match["blame_author"] = author if author is not None else None
                match["blame_time"] = author_time if author_time is not None else None

    return test_issues, shell_issues


def expand_paths(file_args: Optional[List[str]]) -> Optional[List[str]]:
    """Expands glob patterns and directories into a list of file paths."""
    if not file_args:
        return None

    expanded_paths = []

    for item in file_args:
        path = Path(item)

        if "*" in item or "?" in item or "[" in item:
            expanded_paths.extend([str(p) for p in Path().rglob(item)])
        elif path.is_dir():
            expanded_paths.extend([str(p) for p in path.rglob("*.py")])
        elif path.is_file():
            expanded_paths.append(str(path))
        else:
            print(f"Warning: '{item}' does not exist or is not valid.")

    return expanded_paths if expanded_paths else None


def cli():
    """Primary entry point for CLI usage, providing parsing and function calls."""
    parser = argparse.ArgumentParser(description="Python ratchet testing")

    parser.add_argument("-t", "--toml-file", help="specify a .toml file with tests")

    parser.add_argument("-f", "--files", nargs="+", help="specify file(s) to evaluate")

    parser.add_argument(
        "-s", "--shell-only", action="store_true", help="run only shell-based tests"
    )

    parser.add_argument(
        "-r", "--regex-only", action="store_true", help="run only regex-based tests"
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="run verbose tests, printing each infringing line",
    )

    parser.add_argument(
        "-b",
        "--blame",
        action="store_true",
        help="run an additional git-blame for each infraction, ordering results by timestamp",
    )

    parser.add_argument(
        "-m",
        "--max-count",
        type=int,
        help="maximum infractions to display per test (only applies with --blame; default is 10)",
    )

    parser.add_argument(
        "-c",
        "--compare-counts",
        action="store_true",
        help="show only the differences in infraction counts between the current and last saved tests",
    )

    parser.add_argument(
        "-u",
        "--update-ratchets",
        action="store_true",
        help="update ratchets_values.json",
    )

    args = parser.parse_args()
    file: Optional[str] = args.toml_file
    cmd_mode: bool = args.shell_only
    regex_mode: bool = args.regex_only
    update: bool = args.update_ratchets
    compare_counts: bool = args.compare_counts
    blame: bool = args.blame
    verbose: bool = args.verbose
    max_count: Optional[int] = args.max_count
    path_files: List[str] = args.files

    paths = expand_paths(path_files)

    if paths is not None:
        paths = [
            path
            for path in paths
            if Path(path).suffix == ".py" and Path(path).is_file()
        ]

    excludes_path = get_excludes_path()

    mutex_options = [[cmd_mode, regex_mode], [blame, verbose, update, compare_counts]]

    for ls in mutex_options:
        if not ls.count(True) <= 1:
            raise Exception("Mutually exclusive options selected.")

    if not os.path.isfile(excludes_path):
        with open(excludes_path, "a"):
            pass

    if not max_count:
        max_count = 10

    test_path = get_file_path(file)

    if not os.path.isfile(test_path):

        if file is not None and len(file) != 0:
            raise Exception("Specified .toml file not found")

        Path(test_path).touch()
        print(f"\nCreated {test_path}.")
        print("Please add your regex and shell tests there.")
        print("For formatting details see https://github.com/andrewlaack/ratchets\n")
        exit()

    if not os.path.getsize(test_path):
        print("No tests defined...")
        exit()

    if blame:
        issues = evaluate_tests(test_path, cmd_mode, regex_mode, paths)
        print_issues_with_blames(issues, max_count)
    elif compare_counts:
        issues = evaluate_tests(test_path, cmd_mode, regex_mode, paths)
        current_json = json.loads(results_to_json(issues))
        previous_json = load_ratchet_results()
        print_diff(current_json, previous_json)
    elif update:
        update_ratchets(test_path, cmd_mode, regex_mode, paths)
    elif verbose:
        issues = evaluate_tests(test_path, cmd_mode, regex_mode, paths)
        for issue_type in issues:
            print_issues(issue_type)
    else:
        issues = evaluate_tests(test_path, cmd_mode, regex_mode, paths)
        current_json = json.loads(results_to_json(issues))
        print("Current " + str(current_json))
        previous_json = load_ratchet_results()
        print("Previous: " + str(previous_json))
        print("Diffs:")
        print_diff(current_json, previous_json)


if __name__ == "__main__":
    """Entry point when the file is executed directly, envokes CLI method."""
    cli()
