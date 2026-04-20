from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "Output_Files" / "T2_Comparator_Output"


def load_and_validate_yaml_files(
    left_yaml_path: str,
    right_yaml_path: str,
) -> dict[str, dict[str, Any]]:
    """
    Task-2 function #1:
    Load and validate two YAML files produced by Task-1.
    """
    left_path = _validate_yaml_path(left_yaml_path)
    right_path = _validate_yaml_path(right_yaml_path)

    return {
        "left": {
            "path": str(left_path),
            "name": left_path.name,
            "data": _load_yaml_dict(left_path),
        },
        "right": {
            "path": str(right_path),
            "name": right_path.name,
            "data": _load_yaml_dict(right_path),
        },
    }


def identify_name_differences(
    left_yaml_path: str,
    right_yaml_path: str,
    output_path: str | None = None,
) -> list[str]:
    """
    Task-2 function #2:
    Compare KDE names across two YAML files and write differences to a text file.
    """
    loaded = load_and_validate_yaml_files(left_yaml_path, right_yaml_path)
    left_map = _extract_kde_map(loaded["left"]["data"])
    right_map = _extract_kde_map(loaded["right"]["data"])

    name_diffs = sorted(set(left_map.keys()) ^ set(right_map.keys()))
    lines = name_diffs if name_diffs else ["NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"]

    out_file = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _default_output_file(
            left_name=loaded["left"]["name"],
            right_name=loaded["right"]["name"],
            suffix="name-differences.txt",
        )
    )
    _write_lines(out_file, lines)
    return lines


def identify_name_and_requirement_differences(
    left_yaml_path: str,
    right_yaml_path: str,
    output_path: str | None = None,
) -> list[str]:
    """
    Task-2 function #3:
    Compare KDE names and KDE requirements across two YAML files and write tuple output.
    """
    loaded = load_and_validate_yaml_files(left_yaml_path, right_yaml_path)
    left_name = loaded["left"]["name"]
    right_name = loaded["right"]["name"]
    left_map = _extract_kde_map(loaded["left"]["data"])
    right_map = _extract_kde_map(loaded["right"]["data"])

    diff_lines: list[str] = []
    all_names = sorted(set(left_map.keys()) | set(right_map.keys()))

    for kde_name in all_names:
        in_left = kde_name in left_map
        in_right = kde_name in right_map

        if in_left and not in_right:
            diff_lines.append(f"{kde_name},ABSENT-IN-{right_name},PRESENT-IN-{left_name},NA")
            continue

        if in_right and not in_left:
            diff_lines.append(f"{kde_name},ABSENT-IN-{left_name},PRESENT-IN-{right_name},NA")
            continue

        left_requirements = left_map[kde_name]
        right_requirements = right_map[kde_name]

        for req in sorted(left_requirements - right_requirements):
            diff_lines.append(
                f"{kde_name},ABSENT-IN-{right_name},PRESENT-IN-{left_name},{req}"
            )

        for req in sorted(right_requirements - left_requirements):
            diff_lines.append(
                f"{kde_name},ABSENT-IN-{left_name},PRESENT-IN-{right_name},{req}"
            )

    lines = (
        diff_lines
        if diff_lines
        else ["NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"]
    )

    out_file = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _default_output_file(
            left_name=left_name,
            right_name=right_name,
            suffix="name-requirement-differences.txt",
        )
    )
    _write_lines(out_file, lines)
    return lines


def _validate_yaml_path(path_value: str) -> Path:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError("YAML path must be a non-empty string")

    resolved = Path(path_value).expanduser().resolve()
    if resolved.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(f"Expected .yaml or .yml file, got: {resolved}")
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"File not found: {resolved}")
    return resolved


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected top-level YAML object to be a mapping: {path}")
    return loaded


def _extract_kde_map(payload: dict[str, Any]) -> dict[str, set[str]]:
    kde_map: dict[str, set[str]] = {}

    for value in payload.values():
        if not isinstance(value, dict):
            continue

        raw_name = str(value.get("name", "")).strip().lower()
        if not raw_name:
            continue

        raw_requirements = value.get("requirements", [])
        if not isinstance(raw_requirements, list):
            raw_requirements = [raw_requirements]

        normalized_requirements = {
            str(req).strip() for req in raw_requirements if str(req).strip()
        }

        if raw_name not in kde_map:
            kde_map[raw_name] = set()
        kde_map[raw_name].update(normalized_requirements)

    return kde_map


def _default_output_file(left_name: str, right_name: str, suffix: str) -> Path:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    left_stem = Path(left_name).stem
    right_stem = Path(right_name).stem
    return DEFAULT_OUTPUT_DIR / f"{left_stem}-{right_stem}-{suffix}"


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
