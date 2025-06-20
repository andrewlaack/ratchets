# Ratchets

Tests that lazily enforce a requirement across the entire repository.

# What is it?

Ratchets is a lazy way to enforce code compliance on an ongoing basis. This is done by defining regular expressions and shell commands to run against all non-excluded python files in a given repository. Tests only fail when the number of non-compliant lines of code increases. This ensures future code does not have bad patterns, while allowing old code to coexist until it is phased out. 

# Installation

## Required

```bash
pip install ratchets
```

## Optional

**Note:** This is only required if you plan to use Ratchets with PyTest.

```bash
pip install pytest
```

# Usage

First, create a tests.toml file at the root of your repository. See [tests.toml](https://github.com/andrewlaack/ratchets/blob/main/tests.toml) for an example of how this should look. There are two primary rule types that can be defined in the tests.toml file. 

## ratchet.regex

These are tests that check regular expressions for each line of code in each file being examined.

**Example:**

```toml

[ratchet.regex.exceptions]
regex = "except:"
valid = [
  """try:
    x = 1
except ValueError:
    pass""",
  """try:
    do_something()
except (IOError, ValueError):
    handle()"""
]
invalid = [
  """
try:
    pass
except:
    pass""",
  """try:
    dangerous()
except:
    recover()"""
]
description = "Bare except clauses catch all exceptions indiscriminately. This can hide bugs and important exceptions. To mitigate this, explicitly state the exception types that will be handled in the except clause."

```

The valid and invalid entries are not necessary, but we provide a CLI utility, executable with ```python3 -m ratchets.validate```, to verify the regular expressions don't exist in the valid string and do exist in the invalid string. If you are testing a .toml file that is not the repository default, specify it with ```python3 -m ratchets.validate -t FILENAME```. 

The description entry is also optional, but if provided, it will be included in the output of failing PyTest tests.

## ratchet.shell

These are tests that run against each file where each evaluation is of the form:

```bash
FILEPATH | SHELL_COMMAND

```

The standard output of the command is assumed to describe infractions, and the number of lines dictates the total number of infractions. It should also be noted that internally we perform a lookup for the line number based on the standard output. As such, ensure the standard output is the **exact** same text from the line that contains infractions.

**Example:**

```toml

[ratchet.shell.line_too_long]
command = "xargs -n1 awk 'length($0) > 88'"
description = "Black sets the max line-width to 88 to help with the readability of code. Ensure all lines have <89 characters. You can run 'black FILENAME' to fix this issue."

```

This is an example of an `awk` command being used to print each line that has more than 88 characters (this is the default line-length for [black](https://github.com/psf/black)). As these are printed, they are counted as infractions.

## Updating Ratchets

Once your rules are defined, you need to count the infractions. This is done by running.

```bash
python3 -m ratchets -u
```

This creates a ratchet_values.json file in the root of your project. This should be checked into git to manage state.

## Excluding Files

Once the update command has been executed, the `ratchet_excluded.txt` file is created at the root of the repository. By default, this file is empty, but standard .gitignore syntax can be used to specify files that shouldn't be included in tests. Additional files that won't be tested are files specified in your gitignore and files that don't have the extension .py.

## Running as part of PyTest

To set up tests, we provide an example file at [examples/example_test_ratchet.py](https://github.com/andrewlaack/ratchets/blob/main/examples/example_test_ratchet.py), which defines tests to be ran with PyTest. In this file there are two uncommented methods that runs one test per rule in both sections (regex and shell).

The commented methods aggregate these tests together into two total tests (regex and shell).

When creating your PyTest file, ensure it is being indexed by PyTest. If you are unsure what this means, create a file named `test_ratchet.py` in the root of your project.

## Running Tests

Running tests is as simple as running ```pytest``` from the root of the repository or specifying the testing file with ```pytest test_ratchet.py```.

## Additional Functionality

Beyond a seamless integration with PyTest, Ratchets provides functionality to find the location of infringements. This and other functionality can be found by running:

```
python3 -m ratchets --help
```

Where you will see the following help message describing CLI usage for Ratchets:

```
usage: run_tests.py [-h] [-t TOML_FILE] [-f FILES [FILES ...]] [-s] [-r] [-v] [-b] [-m MAX_COUNT] [-c] [-u]

Python ratchet testing

options:
  -h, --help            show this help message and exit
  -t TOML_FILE, --toml-file TOML_FILE
                        specify a .toml file with tests
  -f FILES [FILES ...], --files FILES [FILES ...]
                        specify file(s) to evaluate
  -s, --shell-only      run only shell-based tests
  -r, --regex-only      run only regex-based tests
  -v, --verbose         run verbose tests, printing each infringing line
  -b, --blame           run an additional git-blame for each infraction, ordering results by timestamp
  -m MAX_COUNT, --max-count MAX_COUNT
                        maximum infractions to display per test (only applies with --blame; default is 10)
  -c, --compare-counts  show only the differences in infraction counts between the current and last saved tests
  -u, --update-ratchets
                        update ratchets_values.json
```

# Testing Ratchets Locally

To run the tests for the source code of Ratchets, you can clone this repository with:

```bash
git clone https://github.com/andrewlaack/ratchets/
```

Then `cd` into `ratchets` and run `PyTest`. The tests use the installed version of Ratchets from your virtual environment. This means you must ensure changes to source files are applied to your installed `ratchets` package prior to running the tests.
