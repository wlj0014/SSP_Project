# Author: Will Jones
# date: 3.31.26

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Callable
import yaml
from pypdf import PdfReader


DEFAULT_MODEL_NAME = "google/gemma-3-1b-it"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "Output_files" / "T1_Extractor_Output"


def load_and_validate_documents(doc1_path: str, doc2_path: str) -> dict[str, dict[str, str]]:
    p1 = check_pdf(doc1_path)
    p2 = check_pdf(doc2_path)

    return {
        "doc1": {"path": str(p1), "name": p1.name, "text": read_pdf_text(p1)},
        "doc2": {"path": str(p2), "name": p2.name, "text": read_pdf_text(p2)},
    }


def build_zero_shot_prompt(doc1_name: str, doc1_text: str, doc2_name: str, doc2_text: str) -> str:
    return f"""
You extract Key Data Elements (KDEs) from CIS Kubernetes benchmark recommendations.
Input: a list of recommendation titles, one per line, format `<section> <title> (Automated|Manual)`.
For each recommendation produce one KDE where:
- name MUST be a short noun phrase (2-6 words) copied from the recommendation text.
- requirements MUST be the full recommendation title verbatim.
Do not invent content. Do not summarize or rephrase.

Document 1 Name: {doc1_name}
Document 1 Titles:
{doc1_text}

Document 2 Name: {doc2_name}
Document 2 Titles:
{doc2_text}

Output a single JSON object with this exact shape and nothing else:
{{"doc1": [{{"name": "...", "requirements": ["..."]}}], "doc2": [{{"name": "...", "requirements": ["..."]}}]}}

Respond now with JSON starting with {{
""".strip()


def build_few_shot_prompt(doc1_name: str, doc1_text: str, doc2_name: str, doc2_text: str) -> str:
    return f"""
You extract Key Data Elements (KDEs) from CIS Kubernetes benchmark recommendations.
Input: a list of recommendation titles, one per line, format `<section> <title> (Automated|Manual)`.
The name MUST be a short noun phrase (2-6 words) copied from the recommendation text.
The requirement MUST be the full recommendation title verbatim.
Do not invent content. Do not rephrase.

Example 1:
Document: cis-r1.pdf
Recommendation: 3.2.1 Ensure that the Anonymous Auth is Not Enabled (Automated)
Output KDE: {{"name": "Anonymous Auth", "requirements": ["3.2.1 Ensure that the Anonymous Auth is Not Enabled (Automated)"]}}

Example 2:
Document: cis-r1.pdf
Recommendation: 3.1.1 Ensure that the kubeconfig file permissions are set to 644 or more restrictive (Manual)
Output KDE: {{"name": "kubeconfig file permissions", "requirements": ["3.1.1 Ensure that the kubeconfig file permissions are set to 644 or more restrictive (Manual)"]}}

Now apply the same extraction to every title in the two documents below.

Document 1 Name: {doc1_name}
Document 1 Titles:
{doc1_text}

Document 2 Name: {doc2_name}
Document 2 Titles:
{doc2_text}

Output a single JSON object with this exact shape and nothing else:
{{"doc1": [{{"name": "...", "requirements": ["..."]}}], "doc2": [{{"name": "...", "requirements": ["..."]}}]}}

Respond now with JSON starting with {{
""".strip()


def build_chain_of_thought_prompt(doc1_name: str, doc1_text: str, doc2_name: str, doc2_text: str) -> str:
    return f"""
You extract Key Data Elements (KDEs) from CIS Kubernetes benchmark recommendations.
Input: a list of recommendation titles, one per line, format `<section> <title> (Automated|Manual)`.

Internally reason through these steps without writing them down:
1. For each title, identify the subject noun phrase (2-6 words).
2. Copy the full recommendation title verbatim as the requirement.
3. Collapse identical subjects across titles into a single KDE whose requirements list contains every matching title.

Rules:
- The name MUST be copied from the input titles.
- The requirement MUST be the verbatim full title line.
- Do not invent content. Do not summarize.
- Do not expose your reasoning. Return only the final JSON object.

Document 1 Name: {doc1_name}
Document 1 Titles:
{doc1_text}

Document 2 Name: {doc2_name}
Document 2 Titles:
{doc2_text}

Output a single JSON object with this exact shape and nothing else:
{{"doc1": [{{"name": "...", "requirements": ["..."]}}], "doc2": [{{"name": "...", "requirements": ["..."]}}]}}

Respond now with JSON starting with {{
""".strip()


def identify_kdes_with_prompts(
    doc1_path: str,
    doc2_path: str,
    model_name: str = DEFAULT_MODEL_NAME,
    generator: Callable[[str], str] | None = None,
    max_new_tokens: int = 1024,
) -> dict[str, dict[str, dict[str, Any]]]:

    docs = load_and_validate_documents(doc1_path, doc2_path)
    out_dir = DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    copy_prompt_markdown_to_output(out_dir)

    styles: list[tuple[str, Callable[[str, str], str], Callable[[str, str, str, str], str]]] = [
        ("zero-shot", _build_per_title_zero_shot, build_zero_shot_prompt),
        ("few-shot", _build_per_title_few_shot, build_few_shot_prompt),
        ("chain-of-thought", _build_per_title_chain_of_thought, build_chain_of_thought_prompt),
    ]

    llm = generator if generator is not None else make_llm(model_name, max_new_tokens)

    titles = {
        "doc1": _extract_cis_title_list(docs["doc1"]["text"]),
        "doc2": _extract_cis_title_list(docs["doc2"]["text"]),
    }

    merged: dict[str, dict[str, set[str]]] = {"doc1": {}, "doc2": {}}
    all_runs: list[dict[str, str]] = []

    for style_name, per_title_builder, big_builder in styles:
        per_style_outputs: list[str] = []

        for doc_key in ["doc1", "doc2"]:
            doc_name = docs[doc_key]["name"]
            for title in titles[doc_key]:
                prompt = per_title_builder(doc_name, title)
                raw = llm(prompt)
                per_style_outputs.append(f"[{doc_key}] {title}\n{raw}")

                parsed = _parse_single_kde(raw)
                if parsed is None:
                    continue

                name = str(parsed.get("name", "")).strip().lower()
                if not name:
                    continue

                if name not in merged[doc_key]:
                    merged[doc_key][name] = set()

                reqs = parsed.get("requirements", [])
                if not isinstance(reqs, list):
                    reqs = [str(reqs)]

                for req in reqs:
                    req_clean = str(req).strip()
                    if req_clean:
                        merged[doc_key][name].add(req_clean)

        big_prompt = big_builder(
            docs["doc1"]["name"],
            _extract_cis_titles(docs["doc1"]["text"]),
            docs["doc2"]["name"],
            _extract_cis_titles(docs["doc2"]["text"]),
        )

        all_runs.append(
            {
                "llm_name": model_name,
                "prompt_used": big_prompt,
                "prompt_type": style_name,
                "llm_output": "\n\n---\n\n".join(per_style_outputs),
            }
        )

    final_data = {
        "doc1": to_element_dict(merged["doc1"]),
        "doc2": to_element_dict(merged["doc2"]),
    }

    d1_stem = Path(docs["doc1"]["name"]).stem
    d2_stem = Path(docs["doc2"]["name"]).stem
    doc1_yaml, doc2_yaml = yaml_names(d1_stem, d2_stem, out_dir)

    with doc1_yaml.open("w", encoding="utf-8") as f1:
        yaml.safe_dump(final_data["doc1"], f1, sort_keys=False, allow_unicode=False)

    with doc2_yaml.open("w", encoding="utf-8") as f2:
        yaml.safe_dump(final_data["doc2"], f2, sort_keys=False, allow_unicode=False)

    txt_name = f"{d1_stem}-{d2_stem}-llm-output.txt"
    dump_llm_outputs_to_text(all_runs, str(out_dir / txt_name))

    return final_data


def dump_llm_outputs_to_text(records: list[dict[str, str]], output_path: str) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    text_blocks: list[str] = []
    for rec in records:
        block = (
            "*LLM Name*\n"
            f"{rec.get('llm_name', '')}\n"
            "*Prompt Used*\n"
            f"{rec.get('prompt_used', '')}\n"
            "*Prompt Type*\n"
            f"{rec.get('prompt_type', '')}\n"
            "*LLM Output*\n"
            f"{rec.get('llm_output', '')}\n"
        )
        text_blocks.append(block)

    out.write_text("\n".join(text_blocks), encoding="utf-8")
    return str(out)


def run_all_input_combinations(
    input_dir: str,
    model_name: str = DEFAULT_MODEL_NAME,
    generator: Callable[[str], str] | None = None,
) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    base = Path(input_dir)

    combos = [
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

    results: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for left, right in combos:
        key = f"{Path(left).stem}__{Path(right).stem}"
        results[key] = identify_kdes_with_prompts(
            str(base / left),
            str(base / right),
            model_name=model_name,
            generator=generator,
        )

    return results


def check_pdf(path_value: str) -> Path:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError("Document path must be a non-empty string")

    p = Path(path_value).expanduser().resolve()
    if p.suffix.lower() != ".pdf":
        raise ValueError(f"Expected .pdf, got: {p}")
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")

    with p.open("rb"):
        pass
    return p


def read_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pieces: list[str] = []
    for pg in reader.pages:
        pieces.append(pg.extract_text() or "")
    return "\n".join(pieces).strip()


def make_llm(model_name: str, max_new_tokens: int) -> Callable[[str], str]:
    from transformers import pipeline

    pipe = pipeline("text-generation", model = model_name)

    def run_one(prompt: str) -> str:
        response = pipe(
            prompt,
            max_new_tokens = max_new_tokens,
            return_full_text = False,
            do_sample = False,
        )
        return response[0]["generated_text"]

    return run_one


_CIS_TITLE_PATTERN = re.compile(
    r'(\d+\.\d+\.\d+(?:\.\d+)*)\s+(.+?)\s*\((Automated|Manual)\)'
)

_WS_PATTERN = re.compile(r'\s+')


def _extract_cis_title_list(pdf_text: str) -> list[str]:
    seen: set[str] = set()
    titles: list[str] = []
    for m in _CIS_TITLE_PATTERN.finditer(pdf_text):
        section = m.group(1)
        if section in seen:
            continue
        seen.add(section)
        title = _WS_PATTERN.sub(" ", m.group(2)).strip()
        titles.append(f"{section} {title} ({m.group(3)})")
    return titles


def _extract_cis_titles(pdf_text: str) -> str:
    return "\n".join(_extract_cis_title_list(pdf_text))


def _build_per_title_zero_shot(doc_name: str, title: str) -> str:
    return f"""You extract ONE Key Data Element (KDE) from a single CIS security recommendation.
Rules:
- The name MUST be a short noun phrase (2-6 words) copied from the recommendation text.
- The requirement MUST be the full recommendation text verbatim.
- Do not invent content.
- Do not summarize or rephrase the requirement.

Document: {doc_name}
Recommendation: {title}

Respond with a single JSON object in this exact shape, starting with `{{`:
{{"name": "<noun phrase>", "requirements": ["<full verbatim recommendation>"]}}

Output:"""


def _build_per_title_few_shot(doc_name: str, title: str) -> str:
    return f"""You extract ONE Key Data Element (KDE) from a single CIS security recommendation.
The name MUST be a short noun phrase (2-6 words) copied from the recommendation text.
The requirement MUST be the full recommendation text verbatim.
Do not invent content. Do not rephrase.

Example 1:
Document: cis-r1.pdf
Recommendation: 3.2.1 Ensure that the Anonymous Auth is Not Enabled (Automated)
Output: {{"name": "Anonymous Auth", "requirements": ["3.2.1 Ensure that the Anonymous Auth is Not Enabled (Automated)"]}}

Example 2:
Document: cis-r1.pdf
Recommendation: 3.1.1 Ensure that the kubeconfig file permissions are set to 644 or more restrictive (Manual)
Output: {{"name": "kubeconfig file permissions", "requirements": ["3.1.1 Ensure that the kubeconfig file permissions are set to 644 or more restrictive (Manual)"]}}

Now extract from:
Document: {doc_name}
Recommendation: {title}
Output:"""


def _build_per_title_chain_of_thought(doc_name: str, title: str) -> str:
    return f"""You extract ONE Key Data Element (KDE) from a single CIS security recommendation.
Internally reason through: (1) identify the subject noun phrase (2-6 words), (2) copy the full recommendation verbatim as the requirement. Do not show your reasoning.

Rules:
- The name MUST be a short noun phrase (2-6 words) from the recommendation.
- The requirement MUST be the full recommendation text verbatim.
- Do not invent content.

Document: {doc_name}
Recommendation: {title}

Respond with ONLY a single JSON object in this exact shape:
{{"name": "<noun phrase>", "requirements": ["<full verbatim recommendation>"]}}

Output:"""


def _parse_single_kde(raw_text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(raw_text):
        brace = raw_text.find("{", pos)
        if brace == -1:
            return None
        try:
            obj, end = decoder.raw_decode(raw_text[brace:])
        except json.JSONDecodeError:
            pos = brace + 1
            continue
        if isinstance(obj, dict) and "name" in obj:
            return obj
        pos = brace + end
    return None


def safe_parse_output(raw_text: str) -> dict[str, list[dict[str, Any]]]:
    fixed: dict[str, list[dict[str, Any]]] = {"doc1": [], "doc2": []}
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(raw_text):
        brace = raw_text.find("{", pos)
        if brace == -1:
            break
        try:
            obj, end = decoder.raw_decode(raw_text[brace:])
        except json.JSONDecodeError:
            pos = brace + 1
            continue
        pos = brace + end
        if not isinstance(obj, dict):
            continue
        for doc_key in ["doc1", "doc2"]:
            items = obj.get(doc_key, [])
            if not isinstance(items, list):
                continue
            for one in items:
                if isinstance(one, dict):
                    fixed[doc_key].append(one)
    return fixed


def to_element_dict(merged: dict[str, set[str]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    i = 1

    for kde_name in sorted(merged.keys()):

        out[f"element{i}"] = {
            "name": kde_name,
            "requirements": sorted(merged[kde_name]),
        }

        i += 1

    return out


def yaml_names(stem1: str, stem2: str, output_dir: Path) -> tuple[Path, Path]:

    if stem1 == stem2:
        return output_dir / f"{stem1}-doc1-kdes.yaml", output_dir / f"{stem2}-doc2-kdes.yaml"

    return output_dir / f"{stem1}-kdes.yaml", output_dir / f"{stem2}-kdes.yaml"


def copy_prompt_markdown_to_output(output_dir: Path) -> None:

    project_prompt = Path(__file__).resolve().parents[1] / "PROMPT.md"
    destination = output_dir / "PROMPT.md"

    if project_prompt.exists() and project_prompt.is_file():
        destination.write_text(project_prompt.read_text(encoding="utf-8"), encoding="utf-8")
