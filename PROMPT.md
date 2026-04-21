# PROMPT

## Zero-Shot

You extract Key Data Elements (KDEs) from CIS Kubernetes benchmark recommendations.
Input: a list of recommendation titles, one per line, format `<section> <title> (Automated|Manual)`.
For each recommendation produce one KDE where:
- name = the concise subject of the recommendation (a short noun phrase)
- requirements = the full recommendation title text

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
For each recommendation produce one KDE where name is the concise subject and requirements is the full title text.

Example input:
Document A: User profile shall store full name and email. Password must be at least 12 chars.
Document B: Account must include username, email, and MFA preference.

Example output JSON:
{
  "doc1": [
    {"name": "full name", "requirements": ["User profile shall store full name"]},
    {"name": "email", "requirements": ["User profile shall store email"]},
    {"name": "password", "requirements": ["Password must be at least 12 chars"]}
  ],
  "doc2": [
    {"name": "username", "requirements": ["Account must include username"]},
    {"name": "email", "requirements": ["Account must include email"]},
    {"name": "MFA preference", "requirements": ["Account must include MFA preference"]}
  ]
}

Now do the same for the two documents below.

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
1. Detect each candidate KDE (the subject noun phrase of each title).
2. Normalize synonyms so equivalent subjects collapse to the same name.
3. Map each KDE to every recommendation title that references it.

Do not expose your reasoning. Return only the final JSON object.

Document 1 Name: <doc1_name>
Document 1 Titles:
<doc1_text>

Document 2 Name: <doc2_name>
Document 2 Titles:
<doc2_text>

Output a single JSON object with this exact shape and nothing else:
{"doc1": [{"name": "...", "requirements": ["..."]}], "doc2": [{"name": "...", "requirements": ["..."]}]}

Respond now with JSON starting with {
