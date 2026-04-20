import tempfile
import unittest
from pathlib import Path

import yaml

from src.T2_Comparator import (
    identify_name_and_requirement_differences,
    identify_name_differences,
    load_and_validate_yaml_files,
)


class TestT2Comparator(unittest.TestCase):
    def test_load_and_validate_yaml_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            left = Path(tmp) / "left.yaml"
            right = Path(tmp) / "right.yaml"

            left.write_text(
                yaml.safe_dump(
                    {"element1": {"name": "email", "requirements": ["Req A"]}},
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            right.write_text(
                yaml.safe_dump(
                    {"element1": {"name": "username", "requirements": ["Req B"]}},
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            loaded = load_and_validate_yaml_files(str(left), str(right))

        self.assertEqual(loaded["left"]["name"], "left.yaml")
        self.assertEqual(loaded["right"]["name"], "right.yaml")
        self.assertIn("element1", loaded["left"]["data"])
        self.assertIn("element1", loaded["right"]["data"])

    def test_identify_name_differences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            left = Path(tmp) / "left.yaml"
            right = Path(tmp) / "right.yaml"
            out = Path(tmp) / "name-diffs.txt"

            left.write_text(
                yaml.safe_dump(
                    {
                        "element1": {"name": "email", "requirements": ["Store email"]},
                        "element2": {"name": "account id", "requirements": ["Track account id"]},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            right.write_text(
                yaml.safe_dump(
                    {
                        "element1": {"name": "email", "requirements": ["Store email"]},
                        "element2": {"name": "mfa preference", "requirements": ["Track mfa preference"]},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            lines = identify_name_differences(str(left), str(right), str(out))
            output_lines = out.read_text(encoding="utf-8").splitlines()

        self.assertEqual(lines, output_lines)
        self.assertEqual(set(lines), {"account id", "mfa preference"})

    def test_identify_name_and_requirement_differences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            left = Path(tmp) / "left.yaml"
            right = Path(tmp) / "right.yaml"
            out = Path(tmp) / "name-req-diffs.txt"

            left.write_text(
                yaml.safe_dump(
                    {
                        "element1": {
                            "name": "email",
                            "requirements": ["Store email", "Validate domain"],
                        },
                        "element2": {"name": "account id", "requirements": ["Store account id"]},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            right.write_text(
                yaml.safe_dump(
                    {
                        "element1": {
                            "name": "email",
                            "requirements": ["Store email", "Normalize email"],
                        },
                        "element2": {"name": "username", "requirements": ["Store username"]},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            lines = identify_name_and_requirement_differences(str(left), str(right), str(out))
            output_lines = out.read_text(encoding="utf-8").splitlines()

        expected = {
            "account id,ABSENT-IN-right.yaml,PRESENT-IN-left.yaml,NA",
            "username,ABSENT-IN-left.yaml,PRESENT-IN-right.yaml,NA",
            "email,ABSENT-IN-right.yaml,PRESENT-IN-left.yaml,Validate domain",
            "email,ABSENT-IN-left.yaml,PRESENT-IN-right.yaml,Normalize email",
        }

        self.assertEqual(lines, output_lines)
        self.assertEqual(set(lines), expected)


if __name__ == "__main__":
    unittest.main()
