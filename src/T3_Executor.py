from __future__ import annotations

import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "Output_Files" / "T3_Executor_Output"
DEFAULT_MAPPING_PATH = Path(__file__).resolve().parent / "kde_to_kubescape.yaml"
DEFAULT_YAMLS_ZIP = Path(__file__).resolve().parents[1] / "project-yamls.zip"

NAMES_SENTINEL = "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"
REQS_SENTINEL = "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"
NO_DIFFS_OUTPUT = "NO DIFFERENCES FOUND"


def load_and_validate_txt_files(
    txt1_path: str,
    txt2_path: str,
) -> dict[str, dict[str, Any]]:
    """
    Task-3 function #1:
    Load and validate the two TXT files produced by Task-2.
    txt1_path is the name-differences file.
    txt2_path is the name-and-requirement-differences file.
    """
    names_path = _validate_txt_path(txt1_path)
    reqs_path = _validate_txt_path(txt2_path)

    return {
        "names": {
            "path": str(names_path),
            "name": names_path.name,
            "lines": _read_lines(names_path),
        },
        "name_and_reqs": {
            "path": str(reqs_path),
            "name": reqs_path.name,
            "lines": _read_lines(reqs_path),
        },
    }


def determine_kubescape_controls(
    txt1_path: str,
    txt2_path: str,
    mapping_path: Path | str = DEFAULT_MAPPING_PATH,
    output_path: str | None = None,
) -> str:
    """
    Task-3 function #2:
    Determine the list of Kubescape control IDs to run, based on the
    KDE name and requirement differences emitted by Task-2.
    """
    loaded = load_and_validate_txt_files(txt1_path, txt2_path)
    names_lines = loaded["names"]["lines"]
    reqs_lines = loaded["name_and_reqs"]["lines"]

    out_file = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _default_controls_output_file()
    )
    out_file.parent.mkdir(parents=True, exist_ok=True)

    names_only_sentinel = len(names_lines) == 1 and names_lines[0] == NAMES_SENTINEL
    reqs_only_sentinel = len(reqs_lines) == 1 and reqs_lines[0] == REQS_SENTINEL

    if names_only_sentinel and reqs_only_sentinel:
        out_file.write_text(NO_DIFFS_OUTPUT, encoding="utf-8")
        return str(out_file)

    mapping = _load_mapping(Path(mapping_path))
    kde_names = _extract_kde_names(names_lines, reqs_lines)

    fallback = mapping.get("_fallback", [])
    control_ids: set[str] = set()
    for kde_name in kde_names:
        control_ids.update(mapping.get(kde_name, fallback))

    sorted_ids = sorted(control_ids)
    out_file.write_text("\n".join(sorted_ids), encoding="utf-8")
    return str(out_file)


def run_kubescape(
    controls_txt_path: str,
    yamls_zip_path: Path | str = DEFAULT_YAMLS_ZIP,
) -> pd.DataFrame:
    """
    Task-3 function #3:
    Run the Kubescape CLI against the project YAML files for the chosen
    control IDs, parse the JSON output, and return a DataFrame.
    """
    controls_path = _validate_txt_path(controls_txt_path)
    controls_content = controls_path.read_text(encoding="utf-8").strip()

    zip_path = Path(yamls_zip_path).expanduser().resolve()
    if not zip_path.exists() or not zip_path.is_file():
        raise FileNotFoundError(f"File not found: {zip_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        scan_json = tmp_dir / "scan.json"

        if controls_content == NO_DIFFS_OUTPUT:
            cmd = [
                "kubescape",
                "scan",
                "framework",
                "all",
                str(tmp_dir),
                "--format",
                "json",
                "--output",
                str(scan_json),
            ]
        else:
            control_ids = [
                line.strip()
                for line in controls_content.splitlines()
                if line.strip()
            ]
            joined = ",".join(control_ids)
            cmd = [
                "kubescape",
                "scan",
                "control",
                joined,
                str(tmp_dir),
                "--format",
                "json",
                "--output",
                str(scan_json),
            ]

        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(
                f"kubescape failed (exit {completed.returncode}): {completed.stderr}"
            )

        data = json.loads(scan_json.read_text(encoding="utf-8"))

    return _parse_kubescape_json(data)


def write_results_csv(
    df: pd.DataFrame,
    output_path: str | None = None,
) -> str:
    """
    Task-3 function #4:
    Write the Kubescape results DataFrame to CSV with the required
    6-column header order.
    """
    out_file = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _default_results_output_file()
    )
    out_file.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "FilePath",
        "Severity",
        "Control name",
        "Failed resources",
        "All Resources",
        "Compliance score",
    ]
    df.to_csv(out_file, index=False, columns=columns)
    return str(out_file)


def _validate_txt_path(path_value: str) -> Path:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError("TXT path must be a non-empty string")

    resolved = Path(path_value).expanduser().resolve()
    if resolved.suffix.lower() != ".txt":
        raise ValueError(f"Expected .txt file, got: {resolved}")
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"File not found: {resolved}")
    return resolved


def _read_lines(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8").splitlines()
    return [line.rstrip("\r") for line in raw if line.strip()]


def _load_mapping(mapping_path: Path) -> dict[str, list[str]]:
    if not mapping_path.exists() or not mapping_path.is_file():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

    loaded = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    if loaded is None:
        return {"_fallback": []}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected top-level YAML object to be a mapping: {mapping_path}")

    normalized: dict[str, list[str]] = {}
    for key, value in loaded.items():
        key_norm = str(key).strip().lower()
        if isinstance(value, list):
            normalized[key_norm] = [str(v).strip() for v in value if str(v).strip()]
        else:
            normalized[key_norm] = [str(value).strip()] if str(value).strip() else []

    if "_fallback" not in normalized:
        normalized["_fallback"] = []
    return normalized


def _extract_kde_names(names_lines: list[str], name_req_lines: list[str]) -> set[str]:
    names: set[str] = set()

    for line in names_lines:
        if line == NAMES_SENTINEL:
            continue
        stripped = line.strip()
        if stripped:
            names.add(stripped.lower())

    for line in name_req_lines:
        if line == REQS_SENTINEL:
            continue
        # T2 format: NAME,ABSENT-IN-<f>,PRESENT-IN-<f>,NA|REQ
        # NAME may contain spaces but no commas.
        first_comma = line.find(",")
        if first_comma == -1:
            continue
        raw_name = line[:first_comma].strip()
        if raw_name:
            names.add(raw_name.lower())

    return names


def _parse_kubescape_json(data: dict[str, Any]) -> pd.DataFrame:
    columns = [
        "FilePath",
        "Severity",
        "Control name",
        "Failed resources",
        "All Resources",
        "Compliance score",
    ]

    if not isinstance(data, dict):
        raise RuntimeError(f"unrecognized kubescape JSON schema: type={type(data).__name__}")

    rows: list[dict[str, Any]] = []

    if "results" in data:
        resources_meta = _index_resources(data.get("resources", []))
        summary_controls = _index_summary_controls(data.get("summaryDetails", {}))

        for result in data.get("results", []) or []:
            resource_id = result.get("resourceID", "")
            file_path = _resolve_file_path(resource_id, resources_meta)
            controls_dict = result.get("controls", {}) or {}
            # controls may be a dict keyed by control ID or a list
            control_items = (
                controls_dict.items()
                if isinstance(controls_dict, dict)
                else [(c.get("controlID", ""), c) for c in controls_dict]
            )
            for control_id, control in control_items:
                status_obj = control.get("status", {}) or {}
                status_val = (
                    status_obj.get("status")
                    if isinstance(status_obj, dict)
                    else status_obj
                )
                if status_val and str(status_val).lower() != "failed":
                    continue

                summary = summary_controls.get(control_id, {})
                rows.append(
                    {
                        "FilePath": file_path,
                        "Severity": _severity_for(control, summary),
                        "Control name": control.get("name")
                        or summary.get("name", ""),
                        "Failed resources": _int_or_zero(
                            summary.get("ResourceCounters", {}).get("failedResources")
                            if isinstance(summary.get("ResourceCounters"), dict)
                            else summary.get("failedResources")
                        ),
                        "All Resources": _int_or_zero(
                            _all_resources_from_summary(summary)
                        ),
                        "Compliance score": _float_or_zero(
                            summary.get("complianceScore")
                            or summary.get("score")
                        ),
                    }
                )
        return pd.DataFrame(rows, columns=columns)

    if "frameworks" in data:
        for framework in data.get("frameworks", []) or []:
            for control in framework.get("controls", []) or []:
                status_val = control.get("status", "")
                if status_val and str(status_val).lower() != "failed":
                    continue
                rows.append(
                    {
                        "FilePath": control.get("resourceID", ""),
                        "Severity": _severity_for(control, control),
                        "Control name": control.get("name", ""),
                        "Failed resources": _int_or_zero(
                            control.get("failedResources")
                        ),
                        "All Resources": _int_or_zero(
                            control.get("allResources")
                            or control.get("totalResources")
                        ),
                        "Compliance score": _float_or_zero(
                            control.get("complianceScore")
                            or control.get("score")
                        ),
                    }
                )
        return pd.DataFrame(rows, columns=columns)

    raise RuntimeError(f"unrecognized kubescape JSON schema: keys={list(data.keys())}")


def _index_resources(resources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for res in resources or []:
        rid = res.get("resourceID") or res.get("resourceId") or ""
        if rid:
            indexed[rid] = res
    return indexed


def _index_summary_controls(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    controls = {}
    if isinstance(summary, dict):
        raw = summary.get("controls", {}) or {}
        if isinstance(raw, dict):
            controls = raw
    return controls


def _resolve_file_path(resource_id: str, resources_meta: dict[str, dict[str, Any]]) -> str:
    meta = resources_meta.get(resource_id, {})
    source = meta.get("source", {})
    if isinstance(source, dict):
        path = source.get("path") or source.get("relativePath")
        if path:
            return str(path)
    return str(resource_id)


def _severity_for(control: dict[str, Any], summary: dict[str, Any]) -> Any:
    for key in ("baseScore", "scoreFactor", "severity"):
        if key in control and control.get(key) not in (None, ""):
            return control.get(key)
    for key in ("baseScore", "scoreFactor", "severity"):
        if key in summary and summary.get(key) not in (None, ""):
            return summary.get(key)
    return ""


def _all_resources_from_summary(summary: dict[str, Any]) -> Any:
    counters = summary.get("ResourceCounters") if isinstance(summary, dict) else None
    if isinstance(counters, dict):
        failed = counters.get("failedResources", 0) or 0
        passed = counters.get("passedResources", 0) or 0
        skipped = counters.get("skippedResources", 0) or 0
        return int(failed) + int(passed) + int(skipped)
    return summary.get("allResources") or summary.get("totalResources") or 0


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _default_controls_output_file() -> Path:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_OUTPUT_DIR / "kubescape_controls.txt"


def _default_results_output_file() -> Path:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_OUTPUT_DIR / "t3_results.csv"
