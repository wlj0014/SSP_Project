from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import t3_smoke


NAMES_SENTINEL = "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"
REQS_SENTINEL = "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"

CSV_HEADER = (
    "FilePath,Severity,Control name,Failed resources,All Resources,Compliance score"
)


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_pair(t2_dir: Path, prefix: str, diffs: bool = True) -> None:
    """
    Drop both T2 sibling files for one pair into t2_dir. If diffs=True the
    files include a trivial diff so T3 emits real control IDs; if False only
    the sentinels are written.
    """
    names = t2_dir / f"{prefix}-name-differences.txt"
    reqs = t2_dir / f"{prefix}-name-requirement-differences.txt"
    if diffs:
        _write(names, ["account id"])
        _write(
            reqs,
            ["account id,ABSENT-IN-right.yaml,PRESENT-IN-left.yaml,Store account id"],
        )
    else:
        _write(names, [NAMES_SENTINEL])
        _write(reqs, [REQS_SENTINEL])


class TestDiscoversAllPairs(unittest.TestCase):
    def test_discovers_all_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            t2_dir = work / "t2"
            out_dir = work / "t3"
            t2_dir.mkdir(parents=True)

            prefixes = [
                "cis-r1-cis-r2",
                "cis-r1-cis-r3",
                "cis-r2-cis-r3",
            ]
            for p in prefixes:
                _write_pair(t2_dir, p, diffs=True)

            # Force the stub path (no kubescape CLI) so the test does not
            # depend on whether kubescape is installed on the host.
            with mock.patch.object(t3_smoke.shutil, "which", return_value=None):
                rc = t3_smoke.main(
                    [
                        "--t2-dir",
                        str(t2_dir),
                        "--output-dir",
                        str(out_dir),
                    ]
                )

            self.assertEqual(rc, 0)
            for p in prefixes:
                csv = out_dir / f"{p}-t3-results.csv"
                self.assertTrue(csv.exists(), f"missing {csv}")
                lines = csv.read_text(encoding="utf-8").splitlines()
                self.assertEqual(lines[0], CSV_HEADER)
                controls = out_dir / f"{p}-kubescape-controls.txt"
                self.assertTrue(controls.exists(), f"missing {controls}")


class TestSkipsOrphanedNameDiff(unittest.TestCase):
    def test_skips_orphaned_name_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            t2_dir = work / "t2"
            out_dir = work / "t3"
            t2_dir.mkdir(parents=True)

            # Only the names file is present; no `-name-requirement-differences.txt`.
            _write(t2_dir / "foo-name-differences.txt", ["account id"])

            with mock.patch.object(t3_smoke.shutil, "which", return_value=None):
                rc = t3_smoke.main(
                    [
                        "--t2-dir",
                        str(t2_dir),
                        "--output-dir",
                        str(out_dir),
                    ]
                )

            # No pair was processed successfully -> exit 1, no crash.
            self.assertEqual(rc, 1)
            # Orphan must not have produced a csv.
            self.assertFalse((out_dir / "foo-t3-results.csv").exists())


class TestEmptyT2DirExitsNonzero(unittest.TestCase):
    def test_empty_t2_dir_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            t2_dir = work / "t2"
            out_dir = work / "t3"
            t2_dir.mkdir(parents=True)

            with mock.patch("builtins.print") as mock_print:
                rc = t3_smoke.main(
                    [
                        "--t2-dir",
                        str(t2_dir),
                        "--output-dir",
                        str(out_dir),
                    ]
                )

            self.assertEqual(rc, 1)
            printed = [
                call.args[0]
                for call in mock_print.call_args_list
                if call.args and isinstance(call.args[0], str)
            ]
            self.assertTrue(
                any("no pairs found" in msg for msg in printed),
                f"expected 'no pairs found' in printed output, got: {printed}",
            )


class TestStubWhenKubescapeMissing(unittest.TestCase):
    def test_stub_when_kubescape_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            t2_dir = work / "t2"
            out_dir = work / "t3"
            t2_dir.mkdir(parents=True)

            _write_pair(t2_dir, "cis-r1-cis-r2", diffs=True)

            with mock.patch.object(t3_smoke.shutil, "which", return_value=None):
                rc = t3_smoke.main(
                    [
                        "--t2-dir",
                        str(t2_dir),
                        "--output-dir",
                        str(out_dir),
                    ]
                )

            self.assertEqual(rc, 0)
            csv = out_dir / "cis-r1-cis-r2-t3-results.csv"
            self.assertTrue(csv.exists(), f"missing {csv}")
            lines = csv.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], CSV_HEADER)
            # Exactly one stub row.
            self.assertEqual(len(lines), 2)
            self.assertIn("kubescape CLI not installed", lines[1])


class TestSentinelPair(unittest.TestCase):
    def test_sentinel_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            t2_dir = work / "t2"
            out_dir = work / "t3"
            t2_dir.mkdir(parents=True)

            _write_pair(t2_dir, "cis-r1-cis-r1", diffs=False)

            with mock.patch.object(t3_smoke.shutil, "which", return_value=None):
                rc = t3_smoke.main(
                    [
                        "--t2-dir",
                        str(t2_dir),
                        "--output-dir",
                        str(out_dir),
                    ]
                )

            self.assertEqual(rc, 0)
            controls = out_dir / "cis-r1-cis-r1-kubescape-controls.txt"
            self.assertTrue(controls.exists())
            self.assertEqual(
                controls.read_text(encoding="utf-8").strip(),
                "NO DIFFERENCES FOUND",
            )
            csv = out_dir / "cis-r1-cis-r1-t3-results.csv"
            self.assertTrue(csv.exists())
            lines = csv.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], CSV_HEADER)
            # The stub is written even on the NO DIFFERENCES path because
            # shutil.which is patched to return None.
            self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
