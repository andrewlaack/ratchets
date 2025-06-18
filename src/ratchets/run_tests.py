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


def print_diff(current_json: Dict[str, int], previous_json: Dict[str, int]) -> None:
    all_keys = set(current_json.keys()) | set(previous_json.keys())
    diff_count = 0
    for key in sorted(all_keys):
        current_value = current_json.get(key, 0)
        previous_value = previous_json.get(key, 0)
        if current_value != previous_value:
            diff_count += 1
            diff = current_value - previous_value
            sign = "+" if diff > 0 else "-"
            print(f"  {key}: {previous_value} → {current_value} ({sign}{abs(diff)})")
    if diff_count == 0:
        print("There are no differences.")


def find_project_root(start_path: Optional[str] = None, markers: Optional[List[str]] = None) -> str:
    if start_path is None:
        start_path = os.getcwd()
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


def get_excludes_path() -> str:
    DEFAULT_FILENAME = "ratchet_excluded.txt"
    root = find_project_root(None)
    return os.path.join(root, DEFAULT_FILENAME)


def get_file_path(file: Optional[str]) -> str:
    DEFAULT_FILENAME = "tests.toml"
    if not file:
        file = DEFAULT_FILENAME
    if "/" in file:
        return file
    else:
        root = find_project_root(file)
        return os.path.join(root, file)


def get_python_files(directory: Union[str, Path]) -> List[Path]:
    directory = Path(directory)
    python_files = set([path.absolute() for path in directory.rglob("*.py") if not path.is_symlink()])
    return list(python_files)


def filter_excluded_files(files: List[Path], excluded_path: str, ignore_path: str) -> List[Path]:
    with open(excluded_path, 'r') as f:
        patterns = f.read().splitlines()
    if os.path.isfile(ignore_path):
        with open(ignore_path, 'r') as f:
            patterns += f.read().splitlines()
    spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)
    files = [f for f in files if not spec.match_file(f)]
    return files


def evaluate_tests(path: str, cmd_only: bool, regex_only: bool) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:

    assert os.path.isfile(path)

    config = toml.load(path)

    python_tests = config.get("python-tests")
    custom_tests = config.get("custom-tests")
    root = find_project_root()
    files = get_python_files(root)
    EXCLUDED_PATH = "ratchet_excluded.txt"
    excluded_path = os.path.join(root, EXCLUDED_PATH)
    ignore_path = os.path.join(root, ".gitignore")
    files = filter_excluded_files(files, excluded_path, ignore_path)
    test_issues: Dict[str, List[Dict[str, Any]]] = {}
    custom_issues: Dict[str, List[Dict[str, Any]]] = {}
    if python_tests and not cmd_only:
        test_issues = evaluate_python_tests(files, python_tests) 
    if custom_tests and not regex_only:
        custom_issues = evaluate_command_tests(files, custom_tests) 
    return test_issues, custom_issues


def print_issues(issues: Dict[str, List[Dict[str, Any]]]) -> None:
    for test_name, matches in issues.items():
        if matches:
            print(f"\n{test_name} — matched {len(matches)} issue(s):")
            for match in matches:
                file_path = match['file']
                line = match.get('line')
                content = match['content']
                truncated = content if len(content) <= 80 else content[:80] + "..."
                if line is not None:
                    print(f"  → {file_path}:{line}: {truncated}")
                else:
                    print(f"  → {file_path}: {truncated}")
        else:
            print(f"\n{test_name} — no issues found.")


def load_ratchet_results() -> Dict[str, Any]:

    path = get_ratchet_path()

    if not os.path.isfile(path):
        return {}

    with open(path, 'r') as file:
        data = json.load(file)
    return data


def evaluate_python_tests(files: List[Path], test_str: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    assert len(files) != 0
    assert len(test_str) != 0

    results: Dict[str, List[Dict[str, Any]]] = {}
    threads = []
    results_lock = threading.Lock()

    def eval_thread(test_name: str, rule: Dict[str, Any]):
        pattern = re.compile(rule["regex"])
        matches = []

        for file_path in files:
            with open(file_path, 'r', encoding='utf-8') as f:
                for lineno, line in enumerate(f, 1):
                    if pattern.search(line):
                        matches.append({
                            "file": str(file_path),
                            "line": lineno,
                            "content": line.strip()
                        })
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
    root = find_project_root()
    RATCHET_NAME = "ratchet_values.json"
    ratchet_file_path = os.path.join(root, RATCHET_NAME)
    return ratchet_file_path


def evaluate_command_tests(files: List[Path], test_str: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    assert len(test_str) != 0
    assert len(files) != 0

    results: Dict[str, List[Dict[str, Any]]] = {test_name: [] for test_name in test_str}
    lock = threading.Lock()

    def worker(test_name: str, command_template: str, file_path: str):
        cmd_str = f"echo {file_path} | {command_template}"
        try:
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
                with lock:
                    for line in lines:
                        results[test_name].append({
                            "file": file_path,
                            "line": None,
                            "content": line.strip()
                        })
        except subprocess.TimeoutExpired:
            print(f"Timeout while running test '{test_name}' on {file_path}")

    threads = []

    for test_name, test_dict in test_str.items():
        command_template = test_dict["command"]
        for file_path in files:
            t = threading.Thread(target=worker, args=(test_name, command_template, file_path))
            t.start()
            threads.append(t)

    for t in threads:
        t.join()

    return results


def results_to_json(results: Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]) -> str:
    test_issues, custom_issues = results
    counts: Dict[str, int] = {}
    for name, matches in test_issues.items():
        counts[name] = len(matches)
    for name, matches in custom_issues.items():
        counts[name] = counts.get(name, 0) + len(matches)
    return json.dumps(counts, indent=2, sort_keys=True)


def update_ratchets(test_path: str, cmd_mode: bool, regex_mode: bool) -> None:
    results = evaluate_tests(test_path, cmd_mode, regex_mode)
    results_json = results_to_json(results)
    path = get_ratchet_path()
    with open(path, 'w') as file:
        file.writelines(results_json)


def print_issues_with_blames(results: Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]], max_count: int) -> None:
    enriched_test_issues, enriched_custom_issues = add_blames(results)

    def _parse_time(ts: Optional[str]) -> datetime:
        if not ts:
            return datetime.max
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return datetime.max

    def _print_section(section_name: str, issues_dict: Dict[str, List[Dict[str, Any]]]) -> None:
        for test_name, matches in issues_dict.items():
            if matches:
                sorted_matches = sorted(matches, key=lambda m: _parse_time(m.get("blame_time")))  # type: ignore
                print("\n" + "-" * 40)
                print(f"{section_name} — {test_name} ({len(sorted_matches)} issue{'s' if len(sorted_matches) != 1 else ''}):")
                print("-" * 40)
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
                        print(f"  → {file_path}:{line_no}  by {author} at {ts}")
                        print(f"       {truncated}")
                    else:
                        print(f"  → {file_path}  by {author} at {ts}")
                        print(f"       {truncated}")
            else:
                print(f"\n{section_name} — {test_name}: no issues found.")

    _print_section("Regex Test", enriched_test_issues)
    _print_section("Command Test", enriched_custom_issues)


def add_blames(results: Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    test_issues, custom_issues = results
    try:
        repo_root: Optional[str] = find_project_root()
    except Exception:
        repo_root = None

    def get_blame_for_line(file_path: str, line_no: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
        if repo_root is None:
            return None, None
        cmd = ["git", "blame", "-L", f"{line_no},{line_no}", "--porcelain", file_path]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root, timeout=5)
            if res.returncode != 0:
                return None, None
            author: Optional[str] = None
            author_time: Optional[str] = None
            for l in res.stdout.splitlines():
                if l.startswith("author "):
                    author = l[len("author "):].strip()
                elif l.startswith("author-time "):
                    try:
                        ts = int(l[len("author-time "):].strip())
                        author_time = datetime.fromtimestamp(ts).isoformat()
                    except Exception:
                        author_time = None
                if author is not None and author_time is not None:
                    break
            return author, author_time
        except Exception:
            return None, None

    def get_last_commit_for_file(file_path: str) -> Tuple[Optional[str], Optional[str]]:
        if repo_root is None:
            return None, None
        cmd = ["git", "log", "-1", "--format=%an;%at", "--", file_path]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root, timeout=5)
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

    for issues in (test_issues, custom_issues):
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

    return test_issues, custom_issues




def cli():
    parser = argparse.ArgumentParser(description="Python ratchet testing")

    # Input file
    parser.add_argument("-f", "--file", help="specify .toml file with tests")

    # Filtering modes
    parser.add_argument(
        "-c", "--command-only",
        action="store_true",
        help="run only custom command-based tests"
    )
    parser.add_argument(
        "-r", "--regex-only",
        action="store_true",
        help="run only regex-based tests"
    )

    # Output formatting
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="run verbose tests, printing each infringing line"
    )

    # Blame and related
    parser.add_argument(
        "-b", "--blame",
        action="store_true",
        help="run an additional git-blame for each infraction, ordering results by timestamp"
    )
    parser.add_argument(
        "-m", "--max-count",
        type=int,
        help="maximum infractions to display per test (only applies with --blame; default is 10)"
    )

    # Modes of operation
    parser.add_argument(
        "--compare-counts",
        action="store_true",
        help="show only the differences in infraction counts between the current and last saved tests"
    )
    parser.add_argument(
        "-u", "--update-ratchets",
        action="store_true",
        help="update ratchets_values.json"
    )

    args = parser.parse_args()
    file: Optional[str] = args.file
    cmd_mode: bool = args.command_only
    regex_mode: bool = args.regex_only
    update: bool = args.update_ratchets
    compare_counts: bool = args.compare_counts
    blame: bool = args.blame
    verbose: bool = args.verbose
    max_count: Optional[int] = args.max_count

    excludes_path = get_excludes_path()

    if not os.path.isfile(excludes_path):
        with open(excludes_path, 'a'):
            pass

    if not max_count:
        max_count = 10
    test_path = get_file_path(file)

    # Probably should enforce only
    # one can be selected via an error on
    # the CLI instead of functionally 
    # defining a hierarchy.

    if blame:
        issues = evaluate_tests(test_path, cmd_mode, regex_mode)
        with_blames = add_blames(issues)
        print_issues_with_blames(issues, max_count)
    elif compare_counts:
        issues = evaluate_tests(test_path, cmd_mode, regex_mode)
        current_json = json.loads(results_to_json(issues))
        previous_json = load_ratchet_results()
        print_diff(current_json, previous_json)
    elif update:
        update_ratchets(test_path, cmd_mode, regex_mode)
    elif verbose:
        issues = evaluate_tests(test_path, cmd_mode, regex_mode)
        for issue_type in issues:
            print_issues(issue_type)
    else:
        issues = evaluate_tests(test_path, cmd_mode, regex_mode)
        current_json = json.loads(results_to_json(issues))
        print("Current " + str(current_json))
        previous_json = load_ratchet_results()
        print("Previous: " + str(previous_json))
        print("Diffs:")
        print_diff(current_json, previous_json)

if __name__ == "__main__":
    cli()
