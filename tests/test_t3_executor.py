import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import pandas as pd

from src.T3_Executor import (
    DEFAULT_MAPPING_PATH,
    determine_kubescape_controls,
    load_and_validate_txt_files,
    run_kubescape,
    write_results_csv,
    _load_mapping,
    _parse_kubescape_json,
)


NAMES_SENTINEL = "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"
REQS_SENTINEL = "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def _make_yamls_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "pod.yaml",
            "apiVersion: v1\nkind: Pod\nmetadata:\n  name: demo\n",
        )


class TestLoadAndValidateTxtFiles(unittest.TestCase):
    def test_load_and_validate_txt_files_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            names = Path(tmp) / "names.txt"
            reqs = Path(tmp) / "reqs.txt"
            _write(names, ["account id", "email"])
            _write(reqs, ["account id,ABSENT-IN-right.yaml,PRESENT-IN-left.yaml,NA"])

            loaded = load_and_validate_txt_files(str(names), str(reqs))

        self.assertEqual(loaded["names"]["name"], "names.txt")
        self.assertEqual(loaded["name_and_reqs"]["name"], "reqs.txt")
        self.assertEqual(loaded["names"]["lines"], ["account id", "email"])
        self.assertEqual(
            loaded["name_and_reqs"]["lines"],
            ["account id,ABSENT-IN-right.yaml,PRESENT-IN-left.yaml,NA"],
        )

    def test_load_and_validate_txt_files_bad_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "names.md"
            good = Path(tmp) / "reqs.txt"
            bad.write_text("x", encoding="utf-8")
            good.write_text("x", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_and_validate_txt_files(str(bad), str(good))

    def test_load_and_validate_txt_files_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist.txt"
            good = Path(tmp) / "reqs.txt"
            good.write_text("x", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                load_and_validate_txt_files(str(missing), str(good))

    def test_load_and_validate_txt_files_empty_path(self) -> None:
        with self.assertRaises(ValueError):
            load_and_validate_txt_files("", "")


class TestDetermineKubescapeControls(unittest.TestCase):
    def test_determine_kubescape_controls_no_differences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            names = Path(tmp) / "names.txt"
            reqs = Path(tmp) / "reqs.txt"
            out = Path(tmp) / "controls.txt"
            _write(names, [NAMES_SENTINEL])
            _write(reqs, [REQS_SENTINEL])

            result_path = determine_kubescape_controls(
                str(names), str(reqs), output_path=str(out)
            )
            self.assertEqual(Path(result_path), out)
            content = out.read_text(encoding="utf-8").strip()

        self.assertEqual(content, "NO DIFFERENCES FOUND")

    def test_determine_kubescape_controls_with_diffs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            names = Path(tmp) / "names.txt"
            reqs = Path(tmp) / "reqs.txt"
            out = Path(tmp) / "controls.txt"
            _write(names, ["account id", "service account token"])
            _write(
                reqs,
                [
                    "account id,ABSENT-IN-right.yaml,PRESENT-IN-left.yaml,Store account id",
                ],
            )

            determine_kubescape_controls(
                str(names), str(reqs), output_path=str(out)
            )
            lines = out.read_text(encoding="utf-8").splitlines()

        # account id -> [C-0012, C-0015, C-0261]
        # service account token -> [C-0034, C-0261]
        self.assertEqual(lines, ["C-0012", "C-0015", "C-0034", "C-0261"])

    def test_determine_kubescape_controls_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            names = Path(tmp) / "names.txt"
            reqs = Path(tmp) / "reqs.txt"
            out = Path(tmp) / "controls.txt"
            _write(names, ["totally unknown kde"])
            _write(reqs, [REQS_SENTINEL])

            determine_kubescape_controls(
                str(names), str(reqs), output_path=str(out)
            )
            lines = out.read_text(encoding="utf-8").splitlines()

        # fallback is C-0013, C-0016, C-0012 (sorted: C-0012, C-0013, C-0016)
        self.assertEqual(lines, ["C-0012", "C-0013", "C-0016"])

    def test_determine_kubescape_controls_uses_name_from_tuple(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            names = Path(tmp) / "names.txt"
            reqs = Path(tmp) / "reqs.txt"
            out = Path(tmp) / "controls.txt"
            _write(names, [NAMES_SENTINEL])
            _write(
                reqs,
                [
                    "password,ABSENT-IN-right.yaml,PRESENT-IN-left.yaml,Hash password",
                ],
            )

            determine_kubescape_controls(
                str(names), str(reqs), output_path=str(out)
            )
            lines = out.read_text(encoding="utf-8").splitlines()

        # password -> [C-0012]
        self.assertEqual(lines, ["C-0012"])


class TestLoadMapping(unittest.TestCase):
    def test_load_mapping_includes_fallback(self) -> None:
        mapping = _load_mapping(DEFAULT_MAPPING_PATH)
        self.assertIn("_fallback", mapping)
        self.assertIsInstance(mapping["_fallback"], list)
        self.assertTrue(len(mapping["_fallback"]) > 0)

    def test_load_mapping_lookup_lowercase(self) -> None:
        mapping = _load_mapping(DEFAULT_MAPPING_PATH)
        self.assertIn("account id", mapping)
        self.assertIn("C-0012", mapping["account id"])


class TestRunKubescape(unittest.TestCase):
    def _make_fake_scan_json(self) -> dict:
        return {
            "results": [],
            "resources": [],
            "summaryDetails": {"controls": {}},
        }

    def test_run_kubescape_no_diffs_calls_framework_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            controls = Path(tmp) / "controls.txt"
            controls.write_text("NO DIFFERENCES FOUND", encoding="utf-8")
            zip_path = Path(tmp) / "yamls.zip"
            _make_yamls_zip(zip_path)

            fake_scan = self._make_fake_scan_json()

            def fake_run(cmd, check, capture_output, text):
                # cmd: kubescape scan framework all <tempdir> --format json --output <tempdir>/scan.json
                self.assertEqual(cmd[0], "kubescape")
                self.assertEqual(cmd[1], "scan")
                self.assertEqual(cmd[2], "framework")
                self.assertEqual(cmd[3], "all")
                self.assertIn("--format", cmd)
                self.assertIn("json", cmd)
                self.assertIn("--output", cmd)
                out_idx = cmd.index("--output") + 1
                Path(cmd[out_idx]).write_text(
                    json.dumps(fake_scan), encoding="utf-8"
                )
                return mock.Mock(returncode=0, stdout="", stderr="")

            with mock.patch("src.T3_Executor.subprocess.run", side_effect=fake_run):
                df = run_kubescape(str(controls), yamls_zip_path=str(zip_path))

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(
            list(df.columns),
            [
                "FilePath",
                "Severity",
                "Control name",
                "Failed resources",
                "All Resources",
                "Compliance score",
            ],
        )
        self.assertEqual(len(df), 0)

    def test_run_kubescape_with_controls_calls_scan_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            controls = Path(tmp) / "controls.txt"
            controls.write_text("C-0012\nC-0015\n", encoding="utf-8")
            zip_path = Path(tmp) / "yamls.zip"
            _make_yamls_zip(zip_path)

            fake_scan = {
                "results": [
                    {
                        "resourceID": "pod/demo",
                        "controls": {
                            "C-0012": {
                                "name": "Applications credentials in configuration files",
                                "status": {"status": "failed"},
                            }
                        },
                    }
                ],
                "resources": [
                    {"resourceID": "pod/demo", "source": {"path": "pod.yaml"}}
                ],
                "summaryDetails": {
                    "controls": {
                        "C-0012": {
                            "name": "Applications credentials in configuration files",
                            "baseScore": 7.0,
                            "ResourceCounters": {
                                "failedResources": 1,
                                "passedResources": 0,
                                "skippedResources": 0,
                            },
                            "complianceScore": 50.0,
                        }
                    }
                },
            }

            captured_cmd: list[list[str]] = []

            def fake_run(cmd, check, capture_output, text):
                captured_cmd.append(cmd)
                self.assertEqual(cmd[0], "kubescape")
                self.assertEqual(cmd[1], "scan")
                self.assertEqual(cmd[2], "control")
                self.assertEqual(cmd[3], "C-0012,C-0015")
                out_idx = cmd.index("--output") + 1
                Path(cmd[out_idx]).write_text(
                    json.dumps(fake_scan), encoding="utf-8"
                )
                return mock.Mock(returncode=0, stdout="", stderr="")

            with mock.patch("src.T3_Executor.subprocess.run", side_effect=fake_run):
                df = run_kubescape(str(controls), yamls_zip_path=str(zip_path))

        self.assertEqual(len(captured_cmd), 1)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["FilePath"], "pod.yaml")
        self.assertEqual(df.iloc[0]["Failed resources"], 1)
        self.assertEqual(df.iloc[0]["All Resources"], 1)
        self.assertEqual(df.iloc[0]["Compliance score"], 50.0)

    def test_run_kubescape_raises_on_nonzero_rc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            controls = Path(tmp) / "controls.txt"
            controls.write_text("C-0012", encoding="utf-8")
            zip_path = Path(tmp) / "yamls.zip"
            _make_yamls_zip(zip_path)

            def fake_run(cmd, check, capture_output, text):
                return mock.Mock(returncode=2, stdout="", stderr="boom")

            with mock.patch("src.T3_Executor.subprocess.run", side_effect=fake_run):
                with self.assertRaises(RuntimeError) as ctx:
                    run_kubescape(str(controls), yamls_zip_path=str(zip_path))

        self.assertIn("kubescape failed", str(ctx.exception))
        self.assertIn("boom", str(ctx.exception))


class TestParseKubescapeJson(unittest.TestCase):
    def test_parse_unrecognized_schema(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            _parse_kubescape_json({"foo": "bar"})
        self.assertIn("unrecognized kubescape JSON schema", str(ctx.exception))

    def test_parse_frameworks_shape(self) -> None:
        data = {
            "frameworks": [
                {
                    "controls": [
                        {
                            "resourceID": "pod/demo",
                            "name": "Privileged container",
                            "status": "failed",
                            "severity": "High",
                            "failedResources": 1,
                            "allResources": 1,
                            "complianceScore": 0.0,
                        }
                    ]
                }
            ]
        }
        df = _parse_kubescape_json(data)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Control name"], "Privileged container")


class TestWriteResultsCsv(unittest.TestCase):
    def test_write_results_csv_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "results.csv"
            df = pd.DataFrame(
                [
                    {
                        "FilePath": "pod.yaml",
                        "Severity": 7.0,
                        "Control name": "Example",
                        "Failed resources": 1,
                        "All Resources": 2,
                        "Compliance score": 50.0,
                    }
                ]
            )

            result_path = write_results_csv(df, output_path=str(out))
            self.assertEqual(Path(result_path), out)
            lines = out.read_text(encoding="utf-8").splitlines()

        self.assertEqual(
            lines[0],
            "FilePath,Severity,Control name,Failed resources,All Resources,Compliance score",
        )
        # No index column should be present.
        self.assertFalse(lines[0].startswith(","))

    def test_write_results_csv_empty_df_preserves_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "results.csv"
            df = pd.DataFrame(
                columns=[
                    "FilePath",
                    "Severity",
                    "Control name",
                    "Failed resources",
                    "All Resources",
                    "Compliance score",
                ]
            )
            write_results_csv(df, output_path=str(out))
            lines = out.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            lines[0],
            "FilePath,Severity,Control name,Failed resources,All Resources,Compliance score",
        )


if __name__ == "__main__":
    unittest.main()
