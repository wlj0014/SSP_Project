# SSP_Project

COMP 5700 Secure Software Process — term project, Spring 2026.

We built a pipeline that takes two CIS Kubernetes benchmark PDFs, pulls out the security recommendations as Key Data Elements (KDEs), diffs them, and then runs the relevant Kubescape controls against a set of K8s manifests.

## Team

- Will Jones — wlj0014@auburn.edu
- Devin Kirkland — jdk0075@auburn.edu
- Isaac Summerford — ins0008@auburn.edu

## Model

Gemma-3-1B (`google/gemma-3-1b-it` on HuggingFace)

## How it works

**Task 1 – Extractor.** Reads two PDFs, grabs each CIS recommendation title, and feeds them one at a time to Gemma using three prompt styles (zero-shot, few-shot, chain-of-thought). The results get merged into per-document YAML files and a raw LLM output log.

**Task 2 – Comparator.** Takes the two YAML files from Task 1 and finds what changed — first just by KDE name, then by name + requirement. Each comparison writes a text file.

**Task 3 – Executor.** Maps the differences to Kubescape control IDs (via `src/kde_to_kubescape.yaml`), runs the Kubescape CLI against `project-yamls.zip`, and dumps the scan results to CSV.

The pipeline runs over all nine input pair combinations (cis-r1 through cis-r4).

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # or .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
```

You also need [Kubescape](https://kubescape.io) installed for Task 3 to do real scans. Without it the pipeline still runs but writes a stub CSV.

## Usage

Run everything:
```bash
bash run.sh
```

Run one pair:
```bash
python scripts/ssp_project_main.py inputs/cis-r1.pdf inputs/cis-r2.pdf
```

Run tests:
```bash
pytest --tb=short
```

## Output

Everything lands in `Output_Files/`:

- `T1_Extractor_Output/` — KDE YAML files, LLM output logs, PROMPT.md
- `T2_Comparator_Output/` — diff text files (name-only and name+requirement)
- `T3_Executor_Output/` — Kubescape control lists and result CSVs
