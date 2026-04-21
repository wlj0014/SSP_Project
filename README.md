# SSP_Project
Term project for Secure Software Process COMP 5700.

Extracts Key Data Elements (KDEs) from CIS Kubernetes benchmark PDFs, compares KDEs across documents, and maps differences to Kubescape controls for scanning.

## Members
- Will Jones (wlj0014@auburn.edu)
- Devin Kirkland (jdk0075@auburn.edu)
- Isaac Summerford (ins0008@auburn.edu)

## Model Used
Gemma-3-4B (HuggingFace: `google/gemma-3-4b-it`)

## Quick start
```
python -m venv .venv
source .venv/Scripts/activate    # or: source .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
pytest --tb=short
```
