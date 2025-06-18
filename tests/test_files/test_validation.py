from ratchets import validate
import os

def test_validate_regex():
    current_file_directory = os.path.dirname(os.path.abspath(__file__))
    toml_file_directory_valid = os.path.abspath(os.path.join(current_file_directory, "..", "toml_files/regexp/valid"))
    toml_file_directory_invalid = os.path.abspath(os.path.join(current_file_directory, "..", "toml_files/regexp/invalid"))

    for filename in os.listdir(toml_file_directory_valid):
        full_path = os.path.abspath(os.path.join(toml_file_directory_valid, filename))
        if os.path.isfile(full_path):
            assert validate.validate(full_path), f"{full_path}, was deemed to be invalid"

    for filename in os.listdir(toml_file_directory_invalid):
        full_path = os.path.abspath(os.path.join(toml_file_directory_invalid, filename))

        if os.path.isfile(full_path):
            try:
                validate.validate(full_path)
            except Exception:
                pass
            else:
                assert False, f"Expected validation to fail for {full_path}, but it passed"

if __name__ == "__main__":
    test_validate_regex()
