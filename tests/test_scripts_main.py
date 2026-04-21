from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import run_all_pairs, ssp_project_main


CSV_HEADER = (
    "FilePath,Severity,Control name,Failed resources,All Resources,Compliance score"
)


def _write_fake_yaml(path: Path, kde_name: str) -> None:
    payload = {
        "element1": {
            "name": kde_name,
            "requirements": [f"store {kde_name}"],
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _fake_t1_factory(t1_dir: Path, kde_name: str = "account id"):
    """
    Build a stand-in for identify_kdes_with_prompts that writes the two
    YAML files the ssp_project_main pipeline expects to read next.
    """
    def fake(doc1_path: str, doc2_path: str, **_kwargs):
        stem1 = Path(doc1_path).stem
        stem2 = Path(doc2_path).stem
        if stem1 == stem2:
            y1 = t1_dir / f"{stem1}-doc1-kdes.yaml"
            y2 = t1_dir / f"{stem2}-doc2-kdes.yaml"
        else:
            y1 = t1_dir / f"{stem1}-kdes.yaml"
            y2 = t1_dir / f"{stem2}-kdes.yaml"
        _write_fake_yaml(y1, kde_name)
        _write_fake_yaml(y2, kde_name)
        return {"doc1": {}, "doc2": {}}

    return fake


class TestMainRequiresTwoArgs(unittest.TestCase):
    def test_main_exits_nonzero_without_args(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            ssp_project_main.main([])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_main_exits_nonzero_with_one_arg(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            ssp_project_main.main(["only-one.pdf"])
        self.assertNotEqual(ctx.exception.code, 0)


class TestMainHappyPath(unittest.TestCase):
    def test_happy_path_with_stubs_produces_csv_with_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            t1_dir = work / "Output_files" / "T1_Extractor_Output"
            t2_dir = work / "Output_Files" / "T2_Comparator_Output"
            t3_dir = work / "Output_Files" / "T3_Executor_Output"
            t1_dir.mkdir(parents=True, exist_ok=True)

            pdf1 = work / "cis-r1.pdf"
            pdf2 = work / "cis-r2.pdf"
            pdf1.write_bytes(b"%PDF-fake-1")
            pdf2.write_bytes(b"%PDF-fake-2")

            fake_scan_df = pd.DataFrame(
                [
                    {
                        "FilePath": "pod.yaml",
                        "Severity": 7.0,
                        "Control name": "Applications credentials",
                        "Failed resources": 1,
                        "All Resources": 2,
                        "Compliance score": 50.0,
                    }
                ],
                columns=[
                    "FilePath",
                    "Severity",
                    "Control name",
                    "Failed resources",
                    "All Resources",
                    "Compliance score",
                ],
            )

            with mock.patch.object(
                ssp_project_main, "T1_OUTPUT_DIR", t1_dir
            ), mock.patch.object(
                ssp_project_main, "T2_OUTPUT_DIR", t2_dir
            ), mock.patch.object(
                ssp_project_main, "T3_OUTPUT_DIR", t3_dir
            ), mock.patch.object(
                ssp_project_main,
                "identify_kdes_with_prompts",
                side_effect=_fake_t1_factory(t1_dir),
            ), mock.patch.object(
                ssp_project_main, "shutil"
            ) as mock_shutil, mock.patch.object(
                ssp_project_main, "run_kubescape", return_value=fake_scan_df
            ), mock.patch.object(
                ssp_project_main, "DEFAULT_YAMLS_ZIP", work / "project-yamls.zip"
            ):
                mock_shutil.which.return_value = "/usr/bin/kubescape"
                (work / "project-yamls.zip").write_bytes(b"PK\x03\x04")
                rc = ssp_project_main.main([str(pdf1), str(pdf2)])

            self.assertEqual(rc, 0)
            csv_path = t3_dir / "cis-r1-cis-r2-t3-results.csv"
            self.assertTrue(csv_path.exists(), f"missing {csv_path}")
            lines = csv_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], CSV_HEADER)
            # Controls and T2 outputs should be pair-prefixed.
            self.assertTrue(
                (t3_dir / "cis-r1-cis-r2-kubescape-controls.txt").exists()
            )
            self.assertTrue(
                (t2_dir / "cis-r1-cis-r2-name-differences.txt").exists()
            )
            self.assertTrue(
                (
                    t2_dir / "cis-r1-cis-r2-name-requirement-differences.txt"
                ).exists()
            )


class TestKubescapeAbsentStub(unittest.TestCase):
    def test_kubescape_absent_writes_stub_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            t1_dir = work / "Output_files" / "T1_Extractor_Output"
            t2_dir = work / "Output_Files" / "T2_Comparator_Output"
            t3_dir = work / "Output_Files" / "T3_Executor_Output"
            t1_dir.mkdir(parents=True, exist_ok=True)

            pdf1 = work / "cis-r1.pdf"
            pdf2 = work / "cis-r1.pdf"
            pdf1.write_bytes(b"%PDF-fake-1")

            with mock.patch.object(
                ssp_project_main, "T1_OUTPUT_DIR", t1_dir
            ), mock.patch.object(
                ssp_project_main, "T2_OUTPUT_DIR", t2_dir
            ), mock.patch.object(
                ssp_project_main, "T3_OUTPUT_DIR", t3_dir
            ), mock.patch.object(
                ssp_project_main,
                "identify_kdes_with_prompts",
                side_effect=_fake_t1_factory(t1_dir),
            ), mock.patch.object(
                ssp_project_main, "shutil"
            ) as mock_shutil:
                mock_shutil.which.return_value = None
                rc = ssp_project_main.main([str(pdf1), str(pdf2)])

            self.assertEqual(rc, 0)
            csv_path = t3_dir / "cis-r1-cis-r1-t3-results.csv"
            self.assertTrue(csv_path.exists())
            lines = csv_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], CSV_HEADER)
            # Exactly one data row with the warning message.
            self.assertEqual(len(lines), 2)
            self.assertIn("kubescape CLI not installed", lines[1])
            self.assertIn("N/A", lines[1])


class TestRunAllPairsIterates(unittest.TestCase):
    def test_run_all_pairs_calls_main_nine_times(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = Path(tmp)
            for name in ["cis-r1.pdf", "cis-r2.pdf", "cis-r3.pdf", "cis-r4.pdf"]:
                (inputs / name).write_bytes(b"%PDF")

            call_pairs: list[tuple[str, str]] = []

            def fake_main(argv):
                call_pairs.append((Path(argv[0]).name, Path(argv[1]).name))
                return 0

            with mock.patch.object(
                run_all_pairs.ssp_project_main, "main", side_effect=fake_main
            ):
                rc = run_all_pairs.main([str(inputs)])

            self.assertEqual(rc, 0)
            self.assertEqual(len(call_pairs), 9)
            self.assertEqual(call_pairs, run_all_pairs.PAIR_COMBOS)

    def test_run_all_pairs_reports_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = Path(tmp)
            for name in ["cis-r1.pdf", "cis-r2.pdf", "cis-r3.pdf", "cis-r4.pdf"]:
                (inputs / name).write_bytes(b"%PDF")

            def fake_main(argv):
                # Fail on the very first pair, succeed on the rest.
                left = Path(argv[0]).name
                right = Path(argv[1]).name
                if (left, right) == ("cis-r1.pdf", "cis-r1.pdf"):
                    return 1
                return 0

            with mock.patch.object(
                run_all_pairs.ssp_project_main, "main", side_effect=fake_main
            ):
                rc = run_all_pairs.main([str(inputs)])

            self.assertEqual(rc, 1)

    def test_run_all_pairs_missing_dir(self) -> None:
        rc = run_all_pairs.main(["C:/this/does/not/exist/nope-xyz"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
