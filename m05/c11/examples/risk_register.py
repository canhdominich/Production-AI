RISKS = [
    ("LLM01", "Prompt Injection", "API, Gateway", "separate data from instructions, limit tools", 5, 4),
    ("LLM02", "Sensitive Information Disclosure", "Gateway, PostgreSQL", "tenant in key, masking, access control", 4, 5),
    ("LLM03", "Excessive Agency", "Worker, tools", "least privilege, approve writes", 4, 5),
    ("LLM04", "Supply Chain", "Provider, libraries", "pin versions, check model checksums", 2, 4),
    ("LLM05", "Data and Model Poisoning", "PostgreSQL (pgvector)", "trusted sources, review on ingest", 2, 4),
    ("LLM06", "Unbounded Consumption", "Gateway, Redis", "rate limit, token cap, budget", 5, 4),
    ("LLM07", "Misinformation", "API, user", "citations, quality evaluation", 4, 3),
    ("LLM08", "Hidden Context Exposure", "Gateway", "no secrets in the system prompt", 3, 3),
    ("LLM09", "Vector and Embedding Weaknesses", "PostgreSQL (pgvector)", "filter tenant inside the query", 3, 5),
    ("LLM10", "Improper Output Handling", "API, UI", "context encoding, parameterized SQL", 3, 4),
]

rows = sorted(RISKS, key=lambda r: -(r[4] * r[5]))
print(f"{'id':6}{'risk':36}{'L':>2}{'I':>3}{'score':>6}  where")
for rid, name, where, ctrl, lik, imp in rows:
    print(f"{rid:6}{name:36}{lik:>2}{imp:>3}{lik * imp:>6}  {where}")
top = [r[0] for r in rows[:4]]
print("review first:", ", ".join(top))
