# Ratchets

Tests that lazily enforce a requirement across the entire repo. 

# What is it?

Ratchets is a lazy way to enforce code compliance on an ongoing basis. This is done by defining regular expressions or commands to run against all non-excluded python files in a given repository. Tests pass when the number of non-compliant instances of code decreases and fail when they increase. This ensures that subsequent code does not have bad patterns, while still allowing old code to coexist until it is phased out. 

# Installation

```bash
pip install ratchets
```

# Usage

You first need to create a tests.toml file at the root of your repository. See [tests.toml](tests.toml) for an example of how this should look. There are two primary rule types that can be defined in the tests.toml file. 

## python-tests

These are tests that check regular expressions on the basis of each line of each file being examined.

**Example:**
```toml

[python-tests.exceptions]
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

```

The valid and invalid entries are not necessary, but we provide a CLI utility, ran with ```python3 -m ratchets.validate``` to verify the regular expressions don't exist in the valid string and do exist in the invalid string. If you are testing the tests.toml file in the current git repository or ```python3 -m ratchets.validate -f FILENAME``` if you need to test a specific toml file.


## custom-tests

These are tests that run against each file where each evaluation is of the form:

```bash
FILEPATH | COMMAND

```
It is assumed the standard output of the command describes each of the issues where each line is counted as an infraction.

**Example:**

```toml

[custom-tests.line_too_long]
command = "xargs -n1 awk 'length($0) > 80'"

```

This is an example of an `awk` command being used to print each line that has more than 80 characters. As these are printed, they are counted as infractions.

## Updating Ratchets

Once your rules are defined, you need to count the infractions. This is done by running.

```bash
python3 -m ratchets -u
```

This creates a ratchet_values.json file in the root of your project. This will be checked into git and how the previous number of infractions is tracked to ensure it the never increase.

## Excluding Files

Once you run the update command, you should see a file in the root of your repository titled `ratchet_excluded.txt`. By default, this file is empty, but you can use standard .gitignore syntax to specify files that shouldn't be included in your tests. Additionally, all files specified by the gitignore of your project or that don't have the .py extension will not be included in the evaluation.

## Setting Up Tests

To set up tests, we provide an example file at [examples/example_test_ratchet.py](examples/example_test_ratchet.py), which defines tests to be ran with PyTest. In this file there are two uncommented methods that runs one test per rule in both sections (Python and command).

The commented methods aggregate these tests together into two total tests (Python and command).

When creating your testing file, ensure it is being indexed by pytest. If you are unsure what this means, create a file named `test_ratchet.py` in the root of your project.

## Running Tests

Running tests is as simple as running ```pytest``` from the root of the repository or specifying the testing file with ```pytest test_ratchet.py```.

## Finding Issues

At this point, your project has been set up, but as these tests are ran, and further infringements are found, there is a need to identify them. This, along with many other pieces of functionality can be viewed by running:

```
python -m ratchets --help
```

Where you will see the following help message describing CLI usage for ratchets:

```
usage: __main__.py [-h] [-f FILE] [-c] [-r] [-v] [-b] [-m MAX_COUNT] [--compare-counts] [-u]

Python ratchet testing

options:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  specify .toml file with tests
  -c, --command-only    run only custom command-based tests
  -r, --regex-only      run only regex-based tests
  -v, --verbose         run verbose tests, printing each infringing line
  -b, --blame           run an additional git-blame for each infraction, ordering results by timestamp
  -m MAX_COUNT, --max-count MAX_COUNT
                        maximum infractions to display per test (only applies with --blame; default is 10)
  --compare-counts      show only the differences in infraction counts between the current and last saved tests
  -u, --update-ratchets
                        update ratchets_values.json
```

Of these, the -b option is particularly useful. When PyTests fail due to infringement counts increasing, it is necessary to identify where the new infringement occurred. By using the -b option you will, by default, see the 10 most recent changes that caused infringements for each rule.

# Testing Ratchets Locally

To run the tests for the Ratchets source code locally you can clone this repository with:

```bash
git clone https://github.com/andrewlaack/ratchets/
```

Then `cd` into ratchets and run `PyTest`.
