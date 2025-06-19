import pytest
from ratchets.abstracted_tests import get_regex_tests, get_shell_tests, \
    check_regex_rule, check_shell_rule

@pytest.mark.parametrize("test_name,rule", get_regex_tests().items())
def test_regex_rule(test_name: str, rule: dict) -> None:
    """Runs a test for a single regex rule."""
    check_regex_rule(test_name, rule)

@pytest.mark.parametrize("test_name,test_dict", get_shell_tests().items())
def test_shell_rule(test_name: str, test_dict: dict) -> None:
    """Runs a test for a single shell rule."""
    check_shell_rule(test_name, test_dict)

# def test_all_regex_rules():
#     """Runs a test for all regex rules."""
#     errors = []
#     for test_name, rule in get_regex_tests().items():
#         try:
#             check_regex_rule(test_name, rule)
#         except AssertionError as e:
#             errors.append(f"{test_name}: {e}")
#         except Exception as e:
#             errors.append(f"{test_name}: unexpected error: {e!r}")
#     if errors:
#         pytest.fail("Some regex rules failed:\n" + "\n".join(errors))
# 
# def test_all_shell_rules():
#     """Runs a test for all shell rules."""
#     errors = []
#     for test_name, test_dict in get_shell_tests().items():
#         try:
#             check_shell_rule(test_name, test_dict)
#         except AssertionError as e:
#             errors.append(f"{test_name}: {e}")
#         except Exception as e:
#             errors.append(f"{test_name}: unexpected error: {e!r}")
#     if errors:
#         pytest.fail("Some shell rules failed:\n" + "\n".join(errors))
