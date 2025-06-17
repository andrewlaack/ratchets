import run_tests
import re
import toml
import argparse

# validate rules
def evaluate_single_regex(regex, custom_str):
    pattern = re.compile(regex)
    return pattern.search(custom_str)

def check_valid(python_tests):
    for test in python_tests:
        regex = python_tests[test]["regex"]
        for validation in python_tests[test]["valid"]:
            for line in validation.splitlines():
                if evaluate_single_regex(regex, line):
                    raise AssertionError(f"Regex: {regex} matched {line}")


def check_invalid(python_tests):

    for test in python_tests:
        regex = python_tests[test]["regex"]
        for validation in python_tests[test]["invalid"]:

            found = False

            for line in validation.splitlines():
                if evaluate_single_regex(regex, line):
                    found = True
            
            if not found:
                raise AssertionError(f"Regex: {regex} not matched in {validation}")
    return 0

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Python ratchet testing")
    parser.add_argument("-f", "--file",)

    args = parser.parse_args()
    file = args.file

    test_path = run_tests.get_file_path(file)

    config = toml.load(test_path)
    python_tests = config.get("python-tests")

    if python_tests is None:
        print("No python tests found, there is nothing to validate.")
        exit()

    check_valid(python_tests)
    check_invalid(python_tests)

    print(f"All expected regex invalid/valid samples are correct for:\n{test_path}")
