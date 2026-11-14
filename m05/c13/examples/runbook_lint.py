from datetime import date

TODAY = date(2026, 11, 14)
REQUIRED = ("alert", "impact", "first_checks", "mitigation", "rollback", "escalation", "verify", "owner", "last_drilled")
MAX_AGE_DAYS = 90

draft = [
    {"alert": "ProviderErrorRateHigh: 5xx above 5% for 5 minutes", "impact": "chat answers fail or slow for all branches",
     "first_checks": ["open the Provider dashboard", "check the breaker state"], "mitigation": ["switch to the backup provider"],
     "rollback": [], "escalation": "ask the team", "verify": "", "owner": "Ha", "last_drilled": date(2026, 3, 2)},
    {"alert": "RateLimited429High: 429 above 10% for 10 minutes", "impact": "branches see retries and slow answers",
     "first_checks": ["`curl -s localhost:8080/admin/usage?window=10m`"],
     "mitigation": ["`gateway set tenant_rpm cau-go 30`", "`gateway set max_concurrency 6`"],
     "rollback": ["`gateway set tenant_rpm cau-go 120`"], "escalation": "page the on-call lead after 15 minutes without improvement",
     "verify": "429 rate under 2% for 10 minutes", "owner": "Binh", "last_drilled": date(2026, 11, 2)},
]

repaired = {"alert": "ProviderErrorRateHigh: 5xx or timeout above 5% for 5 minutes", "impact": "chat answers fail or slow for all branches",
            "first_checks": ["`psql -c \"select provider, status, count(*) from usage_events where ts > now() - interval '10 minutes' group by 1, 2\"`",
                             "`curl -s localhost:8080/admin/breakers`"],
            "mitigation": ["`PRIMARY_PROVIDER=provider-b docker compose up -d --no-deps gateway`"],
            "rollback": ["`PRIMARY_PROVIDER=provider-a docker compose up -d --no-deps gateway`"],
            "escalation": "page the on-call lead after 10 minutes without improvement; tell the five branch managers after 20 minutes",
            "verify": "5xx and timeout under 1% for 10 minutes, breaker of provider-a closed", "owner": "Ha", "last_drilled": date(2026, 11, 10)}


def lint(book):
    issues = []
    for entry in book:
        name = entry["alert"].split(":")[0]
        for key in REQUIRED:
            if not entry.get(key):
                issues.append(f"{name}: missing {key}")
        steps = entry.get("first_checks", []) + entry.get("mitigation", []) + entry.get("rollback", [])
        vague = [s for s in steps if "`" not in s]
        if vague:
            issues.append(f"{name}: {len(vague)} step(s) without a command: {vague[0]!r}")
        age = (TODAY - entry["last_drilled"]).days if entry.get("last_drilled") else None
        if age is not None and age > MAX_AGE_DAYS:
            issues.append(f"{name}: last drill {age} days ago, limit {MAX_AGE_DAYS}")
    return issues


for entry, label in ((draft[0], "draft entry 1"), (draft[1], "draft entry 2"), (repaired, "repaired entry 1")):
    problems = lint([entry])
    print(f"{label} ({entry['alert'].split(':')[0]}): {len(problems)} problem(s)")
    for p in problems:
        print("  -", p)
