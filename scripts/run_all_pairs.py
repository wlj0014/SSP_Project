from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import ssp_project_main


PAIR_COMBOS: list[tuple[str, str]] = [
    ("cis-r1.pdf", "cis-r1.pdf"),
    ("cis-r1.pdf", "cis-r2.pdf"),
    ("cis-r1.pdf", "cis-r3.pdf"),
    ("cis-r1.pdf", "cis-r4.pdf"),
    ("cis-r2.pdf", "cis-r2.pdf"),
    ("cis-r2.pdf", "cis-r3.pdf"),
    ("cis-r2.pdf", "cis-r4.pdf"),
    ("cis-r3.pdf", "cis-r3.pdf"),
    ("cis-r3.pdf", "cis-r4.pdf"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_all_pairs",
        description=(
            "Run the full T1 -> T2 -> T3 pipeline over the nine required "
            "PDF pair combinations. Expects the input directory to contain "
            "cis-r1.pdf through cis-r4.pdf."
        ),
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default="inputs",
        help="Directory containing cis-r1.pdf through cis-r4.pdf (default: inputs).",
    )
    args = parser.parse_args(argv)

    base = Path(args.input_dir).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        print(f"ERROR: input directory not found: {base}", file=sys.stderr)
        return 1

    succeeded: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []

    for left, right in PAIR_COMBOS:
        pdf1 = str(base / left)
        pdf2 = str(base / right)
        rc = ssp_project_main.main([pdf1, pdf2])
        if rc == 0:
            succeeded.append((left, right))
        else:
            failed.append((left, right))

    _print_summary(succeeded, failed)
    return 0 if not failed else 1


def _print_summary(
    succeeded: list[tuple[str, str]],
    failed: list[tuple[str, str]],
) -> None:
    print("")
    print("=" * 60)
    print(f"Batch summary: {len(succeeded)} succeeded, {len(failed)} failed")
    print("=" * 60)
    for left, right in succeeded:
        print(f"  OK   {left} x {right}")
    for left, right in failed:
        print(f"  FAIL {left} x {right}")


if __name__ == "__main__":
    raise SystemExit(main())
