import pytest
from ratchets.abstracted_tests import (
    get_regex_tests,
    get_shell_tests,
    check_regex_rule,
    check_shell_rule,
)


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
#     descriptions = []
#     for test_name, rule in get_regex_tests().items():
#         try:
#             check_regex_rule(test_name, rule)
#         except Exception as e:
#             desc = rule['description']
#             if desc is not None:
#                 descriptions.append(test_name + " - " + desc)
#             errors.append(f"{test_name}")
#     if errors:
#         pytest.fail(" - ".join(errors) + "\n\n" + "\n\n".join(descriptions))
#
# def test_all_shell_rules():
#     """Runs a test for all shell rules."""
#     errors = []
#     descriptions = []
#     for test_name, test_dict in get_shell_tests().items():
#         try:
#             check_shell_rule(test_name, test_dict)
#         except Exception as e:
#             desc = test_dict['description']
#             if not desc is None:
#                 desc = "(" + desc + ")"
#                 descriptions.append(test_name + " - " + desc)
#             errors.append(test_name)
#     if errors:
#         pytest.fail(" - ".join(errors) + "\n\n" + "\n\n".join(descriptions))
