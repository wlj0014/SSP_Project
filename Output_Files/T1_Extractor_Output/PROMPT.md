# PROMPT

## Zero-Shot

You are a requirements analyst. Identify key data elements (KDEs) from two documents. A KDE may map to multiple requirements.

Return ONLY valid JSON with this exact top-level structure:
{
  "doc1": [{"name": "...", "requirements": ["req1", "req2"]}],
  "doc2": [{"name": "...", "requirements": ["req1", "req2"]}]
}

Document 1 Name: <doc1_name>
Document 1 Content:
<doc1_text>

Document 2 Name: <doc2_name>
Document 2 Content:
<doc2_text>

## Few-Shot

You are a requirements analyst extracting key data elements (KDEs).
A KDE may map to multiple requirements.

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

Now do the same for the following documents. Return ONLY valid JSON in the same structure.

Document 1 Name: <doc1_name>
Document 1 Content:
<doc1_text>

Document 2 Name: <doc2_name>
Document 2 Content:
<doc2_text>

## Chain-of-Thought

You are a senior requirements analyst.
Internally reason through these steps: (1) detect candidate data elements, (2) normalize synonyms, (3) map each KDE to all relevant requirement statements.
Do not expose internal reasoning. Return only final JSON.

Required output JSON schema:
{
  "doc1": [{"name": "...", "requirements": ["req1", "req2"]}],
  "doc2": [{"name": "...", "requirements": ["req1", "req2"]}]
}

Document 1 Name: <doc1_name>
Document 1 Content:
<doc1_text>

Document 2 Name: <doc2_name>
Document 2 Content:
<doc2_text>
