# PROMPT

The extraction function applies these prompt styles per-title: each CIS recommendation title is sent to the LLM as its own call using a per-title variant of the style below, and all per-title outputs are merged into a single KDE dictionary per document.

## Zero-Shot

You extract Key Data Elements (KDEs) from CIS Kubernetes benchmark recommendations.
Input: a list of recommendation titles, one per line, format `<section> <title> (Automated|Manual)`.
For each recommendation produce one KDE where:
- name MUST be a short noun phrase (2-6 words) copied from the recommendation text.
- requirements MUST be the full recommendation title verbatim.
Do not invent content. Do not summarize or rephrase.

Document 1 Name: <doc1_name>
Document 1 Titles:
<doc1_text>

Document 2 Name: <doc2_name>
Document 2 Titles:
<doc2_text>

Output a single JSON object with this exact shape and nothing else:
{"doc1": [{"name": "...", "requirements": ["..."]}], "doc2": [{"name": "...", "requirements": ["..."]}]}

Respond now with JSON starting with {

## Few-Shot

You extract Key Data Elements (KDEs) from CIS Kubernetes benchmark recommendations.
Input: a list of recommendation titles, one per line, format `<section> <title> (Automated|Manual)`.
The name MUST be a short noun phrase (2-6 words) copied from the recommendation text.
The requirement MUST be the full recommendation title verbatim.
Do not invent content. Do not rephrase.

Example 1:
Document: cis-r1.pdf
Recommendation: 3.2.1 Ensure that the Anonymous Auth is Not Enabled (Automated)
Output KDE: {"name": "Anonymous Auth", "requirements": ["3.2.1 Ensure that the Anonymous Auth is Not Enabled (Automated)"]}

Example 2:
Document: cis-r1.pdf
Recommendation: 3.1.1 Ensure that the kubeconfig file permissions are set to 644 or more restrictive (Manual)
Output KDE: {"name": "kubeconfig file permissions", "requirements": ["3.1.1 Ensure that the kubeconfig file permissions are set to 644 or more restrictive (Manual)"]}

Now apply the same extraction to every title in the two documents below.

Document 1 Name: <doc1_name>
Document 1 Titles:
<doc1_text>

Document 2 Name: <doc2_name>
Document 2 Titles:
<doc2_text>

Output a single JSON object with this exact shape and nothing else:
{"doc1": [{"name": "...", "requirements": ["..."]}], "doc2": [{"name": "...", "requirements": ["..."]}]}

Respond now with JSON starting with {

## Chain-of-Thought

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

Document 1 Name: <doc1_name>
Document 1 Titles:
<doc1_text>

Document 2 Name: <doc2_name>
Document 2 Titles:
<doc2_text>

Output a single JSON object with this exact shape and nothing else:
{"doc1": [{"name": "...", "requirements": ["..."]}], "doc2": [{"name": "...", "requirements": ["..."]}]}

Respond now with JSON starting with {
