import pytest
from ratchets.abstracted_tests import get_python_tests, get_command_tests, check_python_rule, check_command_rule

@pytest.mark.parametrize("test_name,rule", get_python_tests().items())
def test_python_regex_rule(test_name: str, rule: dict) -> None:
    check_python_rule(test_name, rule)

@pytest.mark.parametrize("test_name,test_dict", get_command_tests().items())
def test_custom_command_rule(test_name: str, test_dict: dict) -> None:
    check_command_rule(test_name, test_dict)

    # def test_all_python_regex_rules():
    #     errors = []
    #     for test_name, rule in get_python_tests().items():
    #         try:
    #             check_python_rule(test_name, rule)
    #         except AssertionError as e:
    #             errors.append(f"{test_name}: {e}")
    #         except Exception as e:
    #             errors.append(f"{test_name}: unexpected error: {e!r}")
    #     if errors:
    #         pytest.fail("Some python regex rules failed:\n" + "\n".join(errors))
    # 
    # def test_all_command_rules():
    #     errors = []
    #     for test_name, test_dict in get_command_tests().items():
    #         try:
    #             check_command_rule(test_name, test_dict)
    #         except AssertionError as e:
    #             errors.append(f"{test_name}: {e}")
    #         except Exception as e:
    #             errors.append(f"{test_name}: unexpected error: {e!r}")
    #     if errors:
    #         pytest.fail("Some command rules failed:\n" + "\n".join(errors))
