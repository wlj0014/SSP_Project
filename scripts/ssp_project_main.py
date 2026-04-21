from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.T1_Extractor import identify_kdes_with_prompts
from src.T2_Comparator import (
    identify_name_and_requirement_differences,
    identify_name_differences,
)
from src.T3_Executor import (
    determine_kubescape_controls,
    run_kubescape,
    write_results_csv,
)


T1_OUTPUT_DIR = _REPO_ROOT / "Output_files" / "T1_Extractor_Output"
T2_OUTPUT_DIR = _REPO_ROOT / "Output_Files" / "T2_Comparator_Output"
T3_OUTPUT_DIR = _REPO_ROOT / "Output_Files" / "T3_Executor_Output"
DEFAULT_YAMLS_ZIP = _REPO_ROOT / "project-yamls.zip"

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
    End-to-end entry point for one PDF pair.
    Runs T1 (extract KDEs) -> T2 (compare) -> T3 (map to controls + scan).
    Returns 0 on success, 1 on any caught error.
    """
    parser = argparse.ArgumentParser(
        prog="ssp_project_main",
        description=(
            "Run the T1 -> T2 -> T3 pipeline on a single pair of PDF files. "
            "Outputs land under Output_Files/."
        ),
    )
    parser.add_argument("pdf1", help="Path to the first input PDF.")
    parser.add_argument("pdf2", help="Path to the second input PDF.")
    args = parser.parse_args(argv)

    try:
        csv_path = _run_pipeline(args.pdf1, args.pdf2)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    stem1 = Path(args.pdf1).stem
    stem2 = Path(args.pdf2).stem
    print(f"Pair {stem1} x {stem2} done -> {csv_path}")
    return 0


def _run_pipeline(pdf1: str, pdf2: str) -> str:
    stem1 = Path(pdf1).stem
    stem2 = Path(pdf2).stem

    identify_kdes_with_prompts(pdf1, pdf2)

    yaml1, yaml2 = _t1_yaml_paths(stem1, stem2)
    if not yaml1.exists() or not yaml2.exists():
        raise FileNotFoundError(
            f"Expected T1 YAMLs not found: {yaml1}, {yaml2}"
        )

    T2_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    names_txt = T2_OUTPUT_DIR / f"{stem1}-{stem2}-name-differences.txt"
    reqs_txt = T2_OUTPUT_DIR / f"{stem1}-{stem2}-name-requirement-differences.txt"
    identify_name_differences(str(yaml1), str(yaml2), output_path=str(names_txt))
    identify_name_and_requirement_differences(
        str(yaml1), str(yaml2), output_path=str(reqs_txt)
    )

    T3_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    controls_txt = T3_OUTPUT_DIR / f"{stem1}-{stem2}-kubescape-controls.txt"
    results_csv = T3_OUTPUT_DIR / f"{stem1}-{stem2}-t3-results.csv"

    determine_kubescape_controls(
        str(names_txt), str(reqs_txt), output_path=str(controls_txt)
    )

    df = _scan_or_stub(str(controls_txt))
    write_results_csv(df, output_path=str(results_csv))
    return str(results_csv)


def _scan_or_stub(controls_txt_path: str) -> pd.DataFrame:
    """
    If the kubescape CLI and the project-yamls.zip are available, run a real
    scan. Otherwise return a one-row stub DataFrame with the required headers.
    """
    if shutil.which("kubescape") is None:
        return _stub_dataframe(
            "kubescape CLI not installed - "
            "install from https://kubescape.io to run real scan"
        )

    if not DEFAULT_YAMLS_ZIP.exists():
        return _stub_dataframe(
            f"project-yamls.zip not found at {DEFAULT_YAMLS_ZIP}"
        )

    try:
        return run_kubescape(controls_txt_path, yamls_zip_path=str(DEFAULT_YAMLS_ZIP))
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


def _t1_yaml_paths(stem1: str, stem2: str) -> tuple[Path, Path]:
    if stem1 == stem2:
        return (
            T1_OUTPUT_DIR / f"{stem1}-doc1-kdes.yaml",
            T1_OUTPUT_DIR / f"{stem2}-doc2-kdes.yaml",
        )
    return (
        T1_OUTPUT_DIR / f"{stem1}-kdes.yaml",
        T1_OUTPUT_DIR / f"{stem2}-kdes.yaml",
    )


if __name__ == "__main__":
    raise SystemExit(main())
