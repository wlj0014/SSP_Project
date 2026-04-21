from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.T3_Executor import (
    determine_kubescape_controls,
    run_kubescape,
    write_results_csv,
)


DEFAULT_T2_DIR = _REPO_ROOT / "Output_Files" / "T2_Comparator_Output"
DEFAULT_T3_DIR = _REPO_ROOT / "Output_Files" / "T3_Executor_Output"
DEFAULT_YAMLS_ZIP = _REPO_ROOT / "project-yamls.zip"

NAMES_SUFFIX = "-name-differences.txt"
REQS_SUFFIX = "-name-requirement-differences.txt"

CSV_COLUMNS = [
    "FilePath",
    "Severity",
    "Control name",
    "Failed resources",
    "All Resources",
    "Compliance score",
]


def main(argv: list[str] | None = None) -> int:
    """
    Entry point for the T3-only smoke harness.
    Scans a T2 output directory for paired `-name-differences.txt` and
    `-name-requirement-differences.txt` files and runs T3 across all pairs,
    writing a controls .txt and results .csv per pair.
    """
    parser = argparse.ArgumentParser(
        prog="t3_smoke",
        description=(
            "Run T3 (controls + kubescape scan) over every paired T2 output "
            "on disk. Does not re-run T1 or T2."
        ),
    )
    parser.add_argument(
        "--t2-dir",
        default=str(DEFAULT_T2_DIR),
        help=f"Directory with T2 outputs (default: {DEFAULT_T2_DIR}).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_T3_DIR),
        help=f"Directory to write T3 outputs (default: {DEFAULT_T3_DIR}).",
    )
    parser.add_argument(
        "--yamls-zip",
        default=str(DEFAULT_YAMLS_ZIP),
        help=f"Path to the project YAMLs zip (default: {DEFAULT_YAMLS_ZIP}).",
    )
    args = parser.parse_args(argv)

    t2_dir = Path(args.t2_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    yamls_zip = Path(args.yamls_zip).expanduser().resolve()

    pairs = _discover_pairs(t2_dir)
    if not pairs:
        print("no pairs found")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    failed = 0
    for pair_prefix, names_txt, reqs_txt in pairs:
        try:
            _process_pair(
                pair_prefix=pair_prefix,
                names_txt=names_txt,
                reqs_txt=reqs_txt,
                output_dir=output_dir,
                yamls_zip=yamls_zip,
            )
            processed += 1
            print(f"OK   {pair_prefix}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {pair_prefix}: {exc}", file=sys.stderr)

    print(f"{processed} pairs processed, {failed} failed")
    return 0 if processed > 0 else 1


def _discover_pairs(t2_dir: Path) -> list[tuple[str, Path, Path]]:
    """
    Scan the t2 directory for every `*-name-differences.txt` and pair each with
    its sibling `*-name-requirement-differences.txt`. Returns a list of tuples
    (pair_prefix, names_path, reqs_path) sorted by pair_prefix. Orphaned
    name-differences files (no sibling) are still returned so the caller can
    record them as failures.
    """
    if not t2_dir.exists() or not t2_dir.is_dir():
        return []

    pairs: list[tuple[str, Path, Path]] = []
    for names_path in sorted(t2_dir.glob(f"*{NAMES_SUFFIX}")):
        pair_prefix = names_path.name[: -len(NAMES_SUFFIX)]
        reqs_path = t2_dir / f"{pair_prefix}{REQS_SUFFIX}"
        pairs.append((pair_prefix, names_path, reqs_path))
    return pairs


def _process_pair(
    pair_prefix: str,
    names_txt: Path,
    reqs_txt: Path,
    output_dir: Path,
    yamls_zip: Path,
) -> None:
    if not reqs_txt.exists() or not reqs_txt.is_file():
        raise FileNotFoundError(f"missing sibling {reqs_txt.name}")

    controls_txt = output_dir / f"{pair_prefix}-kubescape-controls.txt"
    results_csv = output_dir / f"{pair_prefix}-t3-results.csv"

    determine_kubescape_controls(
        str(names_txt), str(reqs_txt), output_path=str(controls_txt)
    )

    df = _scan_or_stub(str(controls_txt), yamls_zip)
    write_results_csv(df, output_path=str(results_csv))


def _scan_or_stub(controls_txt_path: str, yamls_zip: Path) -> pd.DataFrame:
    """
    If the kubescape CLI and the yamls zip are available, run a real scan.
    Otherwise return a one-row stub DataFrame with the required headers.
    Mirrors scripts.ssp_project_main._scan_or_stub but takes the zip path as
    an argument so the harness can override it via CLI.
    """
    if shutil.which("kubescape") is None:
        return _stub_dataframe(
            "kubescape CLI not installed - "
            "install from https://kubescape.io to run real scan"
        )

    if not yamls_zip.exists():
        return _stub_dataframe(f"project-yamls.zip not found at {yamls_zip}")

    try:
        return run_kubescape(controls_txt_path, yamls_zip_path=str(yamls_zip))
    except Exception as exc:
        return _stub_dataframe(f"kubescape scan failed: {exc}")


def _stub_dataframe(reason: str) -> pd.DataFrame:
    row = {
        "FilePath": "N/A",
        "Severity": "N/A",
        "Control name": reason,
        "Failed resources": "N/A",
        "All Resources": "N/A",
        "Compliance score": "N/A",
    }
    return pd.DataFrame([row], columns=CSV_COLUMNS)


if __name__ == "__main__":
    raise SystemExit(main())
