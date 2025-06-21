from ratchets.results import TestResult, MatchResult
from ratchets.caching import CachingDatabase, BlameRecord
import queue
from datetime import datetime
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
CACHING_FILENAME = ".ratchet_blame.db"
MAX_THREADS = os.cpu_count() or 1


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
    """Get a list of paths not excluded by the 'excluded_path' or 'ignore_path'."""
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
) -> Tuple[Dict[str, TestResult], Dict[str, TestResult]]:
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

    regex_issues: Dict[str, TestResult] = {}
    shell_issues: Dict[str, TestResult] = {}

    if regex_tests and not cmd_only:
        regex_issues = evaluate_regex_tests(files, regex_tests)
    if shell_tests and not regex_only:
        shell_issues = evaluate_shell_tests(files, shell_tests)
    return regex_issues, shell_issues


def print_issues(results: Dict[str, TestResult]) -> None:
    """Print TestResult objects in a human-readable way."""
    for test_name, tr in results.items():
        num = len(tr.matches)
        if num:
            print(f"\n{test_name} — matched {num} issue{'s' if num != 1 else ''}:")
            for m in tr.matches:
                file_path = m.file
                line = m.line
                content = m.content or ""
                truncated = content if len(content) <= 50 else content[:50] + "..."
                if line is not None:
                    print(f"  -> {file_path}:{line}: {truncated}")
                else:
                    print(f"  -> {file_path}: {truncated}")
        else:
            print(f"\n{test_name} — no issues found.")


def load_ratchet_results(file_location: Optional[str] = None) -> Dict[str, Any]:
    """Load and return current ratchet values.."""

    if file_location is None:
        path = get_ratchet_path()
    else:
        path = file_location

    if not os.path.isfile(path):
        return {}

    with open(path, "r") as file:
        data = json.load(file)

    return dict(data)


def evaluate_regex_tests(
    files: List[Path], test_str: Dict[str, Dict[str, Any]]
) -> Dict[str, TestResult]:
    """Evaluate a list of regex tests in parallel with one thread per test."""
    if not files:
        raise Exception("No files were passed in to be evaluated.")
    if not test_str:
        raise Exception("No regex tests were passed in to be evaluated.")

    results: Dict[str, TestResult] = {}
    threads = []
    results_lock = threading.Lock()

    def eval_thread(test_name: str, rule: Dict[str, Any]):
        """Evaluate a single regular expression across all specified files."""
        pattern = re.compile(rule["regex"])
        tr = TestResult(name=test_name, matches=[])

        for file_path in files:
            with open(file_path, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if pattern.search(line):
                        mr = MatchResult(
                            file=str(file_path),
                            line=lineno,
                            content=line.strip(),
                        )
                        tr.matches.append(mr)
                        # or: tr.add_match(mr) if you’ve defined that

        with results_lock:
            results[test_name] = tr

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
) -> Dict[str, TestResult]:
    """Evaluate all shell tests in parallel."""
    if not test_str:
        raise Exception("No shell tests passed to evaluation method.")
    if not files:
        raise Exception("No files passed to evaluation method.")

    results: Dict[str, TestResult] = {
        test_name: TestResult(name=test_name, matches=[]) for test_name in test_str
    }
    lock = threading.Lock()

    file_strs = [str(p) for p in files]
    file_lines_map: Dict[str, Dict[str, List[int]]] = build_file_lines_map(file_strs)

    def worker(test_name: str, shell_template: str, file_path: Path):
        file_str = str(file_path)
        cmd_str = f"echo {file_str} | {shell_template}"
        try:
            res = subprocess.run(
                cmd_str, shell=True, text=True, capture_output=True, timeout=5
            )
            output = res.stdout.strip()
            if output:
                lines = output.splitlines()
                with lock:
                    tr = results[test_name]
                    for line in lines:
                        content = line.rstrip("\n")
                        line_numbers = file_lines_map[file_str].get(content, [])
                        if line_numbers:
                            ln = line_numbers.pop(0)
                            mr = MatchResult(
                                file=file_str,
                                line=ln,
                                content=content,
                            )
                            tr.matches.append(mr)
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
    results: Tuple[Dict[str, TestResult], Dict[str, TestResult]],
) -> Dict[str, int]:
    """
    Convert test results (regex and shell) to a JSON-serializable dict of counts.
    """
    regex_results, shell_results = results
    counts: Dict[str, int] = {}

    for name, tr in regex_results.items():
        counts[name] = len(tr.matches)

    for name, tr in shell_results.items():
        counts[name] = counts.get(name, 0) + len(tr.matches)

    return counts


def update_ratchets(
    test_path: str,
    cmd_mode: bool,
    regex_mode: bool,
    paths: Optional[List[str]],
    override_ratchet_path: Optional[str] = None,
) -> None:
    """Update the current ratchets based on 'test_path'."""
    results = evaluate_tests(test_path, cmd_mode, regex_mode, paths)
    results_json = results_to_json(results)

    if override_ratchet_path is None:
        path = get_ratchet_path()
    else:
        path = override_ratchet_path

    with open(path, "w") as file:
        file.writelines(results_json)


def print_issues_with_blames(
    results: Tuple[Dict[str, TestResult], Dict[str, TestResult]],
    max_count: int,
) -> None:
    """
    Enriches each TestResult with blame info, then prints in human-readable format.
    Expects:
      results: (regex_results, shell_results), each Dict[str, TestResult].
    """
    # Assume add_blames has been updated to accept and return Dict[str, TestResult]:
    enriched_regex, enriched_shell = add_blames(results)

    def _parse_time_obj(ts: Optional[Union[datetime, str]]) -> datetime:
        """Convert datetime or ISO-string to datetime, with fallback."""
        if ts is None:
            return datetime.min
        if isinstance(ts, datetime):
            return ts
        # assume ISO string
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return datetime.min

    def _print_section(section_name: str, results_dict: Dict[str, TestResult]) -> None:
        for test_name, tr in results_dict.items():
            matches = tr.matches
            if matches:
                # sort by blame_time descending: None/invalid → treated as oldest
                sorted_matches = sorted(
                    matches,
                    key=lambda m: _parse_time_obj(m.blame_time),
                    reverse=True,
                )
                total = len(sorted_matches)
                print()
                print(
                    f"{section_name} — {test_name}" +
                        f" ({total} issue{'s' if total != 1 else ''}):"
                )
                print()
                for i, m in enumerate(sorted_matches):
                    if i >= max_count:
                        break
                    file_path = m.file or "<unknown>"
                    line_no = m.line
                    content = (m.content or "").strip()
                    truncated = content if len(content) <= 80 else content[:80] + "..."
                    author = m.blame_author or "Unknown"
                    ts_obj = m.blame_time
                    ts_str = (
                        ts_obj.isoformat()
                        if isinstance(ts_obj, datetime)
                        else (ts_obj or "Unknown")
                    )
                    if line_no is not None:
                        print(f"  -> {file_path}:{line_no}  by {author} at {ts_str}")
                        print(f"       {truncated}")
                    else:
                        print(
                        f"  -> {file_path}  file last updated by {author} at {ts_str}"
                        )
                        print(f"       {truncated}")
            else:
                print(f"\n{section_name} — {test_name}: no issues found.")

    _print_section("Regex Test", enriched_regex)
    _print_section("Shell Test", enriched_shell)


def add_blames(
    results: Tuple[Dict[str, TestResult], Dict[str, TestResult]],
) -> Tuple[Dict[str, TestResult], Dict[str, TestResult]]:
    """Add blame information to TestResult inputs, enriching each MatchResult."""
    regex_results, shell_results = results

    try:
        repo_root: Optional[str] = find_project_root()
    except Exception:
        repo_root = None

    db_path = os.path.join(str(repo_root), CACHING_FILENAME)
    db = CachingDatabase(db_path)

    new_records: List[BlameRecord] = []
    needs_blame: List[Tuple[MatchResult, str, int, str]] = []

    # Serial cache lookup
    for results_dict in (regex_results, shell_results):
        for test_name, tr in results_dict.items():
            for m in tr.matches:
                file_path = m.file
                line_content = m.content
                assert line_content is not None

                line_no = m.line
                if not file_path:
                    continue
                if line_no is None:
                    raise LookupError(f"No line found matching: {line_content}")

                if repo_root is not None:
                    blame_res: Optional[BlameRecord] = db.get_blame(line_no, file_path)
                    if blame_res is not None and blame_res.line_content == line_content:
                        # Use datetime from cache
                        m.blame_author = blame_res.author
                        # blame_res.timestamp is datetime (per CachingDatabase API)
                        m.blame_time = (
                            blame_res.timestamp
                            if isinstance(blame_res.timestamp, datetime)
                            else None
                        )
                        continue
                # Needs fresh blame
                needs_blame.append((m, file_path, line_no, line_content))

    if needs_blame:
        task_q = queue.Queue()
        for item in needs_blame:
            task_q.put(item)

        def worker():
            while True:
                try:
                    m, file_path, line_no, line_content = task_q.get(block=False)
                except queue.Empty:
                    break

                author: Optional[str] = None
                parsed_time: Optional[datetime] = None

                if repo_root is not None:
                    try:
                        cmd = [
                            "git",
                            "blame",
                            "-L",
                            f"{line_no},{line_no}",
                            "--porcelain",
                            file_path,
                        ]
                        res = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            cwd=repo_root,
                            timeout=5,
                        )
                        if res.returncode == 0:
                            parsed_author: Optional[str] = None
                            parsed_ts: Optional[datetime] = None
                            for line in res.stdout.splitlines():
                                if line.startswith("author "):
                                    parsed_author = line[len("author ") :].strip()
                                elif line.startswith("author-time "):
                                    try:
                                        ts_int = int(
                                            line[len("author-time ") :].strip()
                                        )
                                        parsed_ts = datetime.fromtimestamp(ts_int)
                                    except Exception:
                                        parsed_ts = None
                                if parsed_author is not None and parsed_ts is not None:
                                    break
                            if parsed_author is not None and parsed_ts is not None:
                                author = parsed_author
                                parsed_time = parsed_ts
                                # Record for cache
                                new_records.append(
                                    BlameRecord(
                                        line_content=line_content,
                                        line_number=int(line_no),
                                        timestamp=parsed_ts,
                                        file_name=file_path,
                                        author=parsed_author,
                                    )
                                )
                        else:
                            # optionally print stderr
                            print(res.stderr, end="")
                    except Exception:
                        pass

                # Set on the MatchResult
                m.blame_author = author
                m.blame_time = parsed_time
                task_q.task_done()

        num_tasks = task_q.qsize()
        num_threads = min(MAX_THREADS, num_tasks) if num_tasks > 0 else 0
        threads: List[threading.Thread] = []
        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            t.daemon = True
            t.start()
            threads.append(t)
        task_q.join()
        for t in threads:
            t.join()

    if new_records:
        db.create_or_update_blames(new_records)

    return regex_results, shell_results


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
        help="run an additional git-blame for"
        + "each infraction, ordering results by timestamp",
    )

    parser.add_argument(
        "--clear-cache", action="store_true", help="clear the blame cache"
    )

    parser.add_argument(
        "-m",
        "--max-count",
        type=int,
        help="maximum infractions to display per test"
        + "(only applies with --blame; default is 10)",
    )

    parser.add_argument(
        "-c",
        "--compare-counts",
        action="store_true",
        help="show only the differences in infraction "
        + "counts between the current and last saved tests",
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
    clear_cache: bool = args.clear_cache
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

    if (paths is None or len(paths) == 0) and path_files is not None:
        raise FileNotFoundError("No .py files found in the specified locations.")

    excludes_path = get_excludes_path()

    mutex_options = [
        [cmd_mode, regex_mode, clear_cache],
        [blame, verbose, update, compare_counts, clear_cache],
    ]

    for ls in mutex_options:
        if not ls.count(True) <= 1:
            raise Exception("Mutually exclusive options selected.")

    if clear_cache:
        repo_root = find_project_root()
        db_path = os.path.join(str(repo_root), CACHING_FILENAME)
        db = CachingDatabase(db_path)
        db.clear_cache()
        print("Cache cleared.")
        return

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
        current_json = results_to_json(issues)
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
        current_json = results_to_json(issues)
        print("Current " + str(current_json))
        previous_json = load_ratchet_results()
        print("Previous: " + str(previous_json))
        print("Diffs:")
        print_diff(current_json, previous_json)


def process_file(file_path: str) -> Dict[str, List[int]]:
    """Read a file and build a map."""
    file_map: Dict[str, List[int]] = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            normalized = line.rstrip("\n")
            file_map.setdefault(normalized, []).append(idx)
    return file_map


# After comparing this and a parallelized version; this runs faster.
# The parallel version used threading which imposed an overhead cost
# so it may be possible to speed this up, but it is not obvious.


def build_file_lines_map(files: List[str]) -> Dict[str, Dict[str, List[int]]]:
    """
    Process files serially, returning a dict mapping file_path to its line-content map.
    """
    file_lines_map: Dict[str, Dict[str, List[int]]] = {}
    for fp in files:
        try:
            file_map = process_file(fp)
            file_lines_map[fp] = file_map
        except Exception as e:
            raise Exception(f"Error reading {fp}: {e}")
    return file_lines_map


if __name__ == "__main__":
    """Entry point when the file is executed directly, envokes CLI method."""
    cli()
