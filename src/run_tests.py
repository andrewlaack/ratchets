import os
import pathspec
from datetime import datetime
from pathlib import Path
import toml
import argparse
import json
import re
import subprocess

def print_diff(current_json, previous_json):
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

def find_project_root(start_path=None, markers=None):
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

def filter_excluded_files(files, excluded_path, ignore_path):
    with open(excluded_path, 'r') as f:
        patterns = f.read().splitlines()

    if os.path.isfile(ignore_path):
        with open(ignore_path, 'r') as f:
            patterns += f.read().splitlines()

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

    ignore_path = os.path.join(root, ".gitignore")

    files = filter_excluded_files(files, excluded_path, ignore_path)

    test_issues = {}
    custom_issues = {}

    if python_tests and not cmd_only:
        test_issues = evaluate_python_tests(files, python_tests)

    if custom_tests and not regex_only:
        custom_issues = evaluate_command_tests(files, custom_tests)

    return (test_issues, custom_issues)

def print_issues(issues):
    for test_name, matches in issues.items():
        if matches:
            print(f"\n{test_name} — matched {len(matches)} issue(s):")
            for match in matches:
                file = match['file']
                line = match.get('line')
                content = match['content']
                truncated = content if len(content) <= 80 else content[:80] + "..."
                if line is not None:
                    print(f"  → {file}:{line}: {truncated}")
                else:
                    print(f"  → {file}: {truncated}")
        else:
            print(f"\n{test_name} — no issues found.")


def load_ratchet_results():
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


def evaluate_command_tests(files, test_str):
    assert len(test_str) != 0
    assert len(files) != 0

    results = {}

    for test_name, test_dict in test_str.items():
        command_template = test_dict["command"]
        results[test_name] = []

        for file in files:
            cmd_str = f"echo {file} | {command_template}"

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
                    for line in lines:
                        results[test_name].append({
                            "file": str(file),
                            "line": None,
                            "content": line.strip()
                        })

            except subprocess.TimeoutExpired:
                print(f"Timeout while running test '{test_name}' on {file}")
    return results

def results_to_json(results):

    test_issues, custom_issues = results
    counts = {}

    for name, matches in test_issues.items():
        counts[name] = len(matches)

    for name, matches in custom_issues.items():
        counts[name] = counts.get(name, 0) + len(matches)

    return json.dumps(counts, indent=2, sort_keys=True)

def update_ratchets(test_path, cmd_mode, regex_mode):
    results = evaluate_tests(test_path, cmd_mode, regex_mode)
    results_json = results_to_json(results)
    path = get_ratchet_path()
    with open(path, 'w') as file:
        file.writelines(results_json)



from datetime import datetime

def print_issues_with_blames(results, max_count):
    enriched_test_issues, enriched_custom_issues = add_blames(results)

    def _parse_time(ts):
        if not ts:
            return datetime.max
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return datetime.max

    def _print_section(section_name, issues_dict):
        for test_name, matches in issues_dict.items():
            if matches:
                sorted_matches = sorted(matches, key=lambda m: _parse_time(m.get("blame_time")))
                print("\n" + "-"*40)
                print(f"{section_name} — {test_name} ({len(sorted_matches)} issue{'s' if len(sorted_matches)!=1 else ''}):")
                print("-"*40)
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
                # No matches for this test
                print(f"\n{section_name} — {test_name}: no issues found.")

    _print_section("Regex Test", enriched_test_issues)
    _print_section("Command Test", enriched_custom_issues)

def add_blames(results):

    test_issues, custom_issues = results

    # Determine repo root to run git commands in
    try:
        repo_root = find_project_root()
    except Exception:
        repo_root = None  # if not in a git repo, blame will fail

    def get_blame_for_line(file_path, line_no):
        """
        Returns (author, timestamp_iso) for a given file and line number via git blame.
        If anything fails, returns (None, None).
        """
        if repo_root is None:
            return None, None
        # Use porcelain format for easier parsing
        cmd = ["git", "blame", "-L", f"{line_no},{line_no}", "--porcelain", file_path]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root, timeout=5)
            if res.returncode != 0:
                return None, None
            author = None
            author_time = None
            for l in res.stdout.splitlines():
                if l.startswith("author "):
                    author = l[len("author "):].strip()
                elif l.startswith("author-time "):
                    # author-time is a Unix timestamp (seconds since epoch)
                    try:
                        ts = int(l[len("author-time "):].strip())
                        # convert to ISO 8601; uses local timezone
                        author_time = datetime.fromtimestamp(ts).isoformat()
                    except Exception:
                        author_time = None
                # once we have both, we can break
                if author is not None and author_time is not None:
                    break
            return author, author_time
        except Exception:
            return None, None

    def get_last_commit_for_file(file_path):
        """
        Returns (author, timestamp_iso) for the last commit touching this file via git log.
        If fails, returns (None, None).
        """
        if repo_root is None:
            return None, None
        cmd = ["git", "log", "-1", "--format=%an;%at", "--", file_path]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root, timeout=5)
            if res.returncode != 0 or not res.stdout.strip():
                return None, None
            out = res.stdout.strip()
            # format is "Author Name;timestamp"
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

    # Process both test_issues and custom_issues
    for issues in (test_issues, custom_issues):
        for test_name, matches in issues.items():
            for match in matches:
                file_path = match.get("file")
                line_no = match.get("line")
                # Only proceed if file_path exists
                if not file_path:
                    continue
                # If it's an absolute path, convert to relative to repo_root if possible
                # Git commands accept absolute paths if cwd is repo root, so this is OK.
                if line_no is not None:
                    # try blame for the specific line
                    author, author_time = get_blame_for_line(file_path, line_no)
                else:
                    # fallback to last commit touching file
                    author, author_time = get_last_commit_for_file(file_path)
                # Attach blame info if found
                if author is not None:
                    match["blame_author"] = author
                else:
                    match["blame_author"] = None
                if author_time is not None:
                    match["blame_time"] = author_time
                else:
                    match["blame_time"] = None

    return (test_issues, custom_issues)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Python ratchet testing")
    parser.add_argument("-f", "--file", help="Specify .toml file with tests")

    parser.add_argument(
        "-b", "--blame",
        action="store_true",
        help="Run only custom command-based tests"
    )

    parser.add_argument(
        "--max-count", "-m",
        type=int,
        default=None,
        help="Maximum infractions to display per test (only applies with --blame; default is 10)"
    )

    parser.add_argument(
        "-c", "--command-only",
        action="store_true",
        help="Run only custom command-based tests"
    )


    parser.add_argument(
        "--compare-counts",
        action="store_true",
        help="Compare the counts between the current test and the last saved"
    )

    parser.add_argument(
        "-r", "--regex-only",
        action="store_true",
        help="Run only regex-based tests"
    )

    parser.add_argument(
        "-u", "--update-ratchets",
        action="store_true",
        help="Update ratchets_values.json"
    )

    args = parser.parse_args()
    file = args.file

    cmd_mode = args.command_only
    regex_mode = args.regex_only
    update = args.update_ratchets
    compare_counts = args.compare_counts
    blame = args.blame
    max_count = args.max_count

    if not max_count:
        max_count = 10

    test_path = get_file_path(file)

    if blame:
        issues = evaluate_tests(test_path, cmd_mode, regex_mode)
        with_blames = add_blames(issues)
        print_issues_with_blames(issues, max_count)

    else:
        if compare_counts:
            issues = evaluate_tests(test_path, cmd_mode, regex_mode)

            current_json = json.loads(results_to_json(issues))
            previous_json = load_ratchet_results()

            print_diff(current_json, previous_json)

        else:
            if update:
                update_ratchets(test_path, cmd_mode, regex_mode)
            else:
                issues = evaluate_tests(test_path, cmd_mode, regex_mode)
                for issue_type in issues:
                    print_issues(issue_type)
