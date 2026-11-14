
def triage(case):
    if case.get("workplace_emotion_recognition") or case.get("social_scoring"):
        return "prohibited", "banned practice, applied since 2 Feb 2025"
    if case.get("employment_decisions") or case.get("credit_scoring") or case.get("education_scoring"):
        return "high-risk (Annex III)", "strict obligations from 2 Dec 2027: risk management, data quality, logging, human oversight"
    if case.get("talks_to_people") or case.get("generates_public_content"):
        return "transparency", "tell people they talk to AI, label AI content (Article 50), from 2 Aug 2026"
    return "minimal", "no specific AI Act obligation; keep good practice and AI literacy"


CASES = [
    ("Chat support used by branch staff only", {"talks_to_people": False}),
    ("Chat widget answering customers directly", {"talks_to_people": True}),
    ("Knowledge assistant on internal policy", {}),
    ("Weekly report agent for managers", {}),
    ("Score couriers to decide pay and discipline", {"employment_decisions": True}),
    ("Camera that reads courier mood at the depot", {"workplace_emotion_recognition": True}),
]
for name, flags in CASES:
    tier, why = triage(flags)
    print(f"{name:46s}{tier:22s}{why}")

print()
SOURCE = "digital-strategy.ec.europa.eu AI Act page and AI Act Service Desk timeline, read 2026-11-14"
DATES = [("2025-02-02", "prohibitions, AI literacy"), ("2025-08-02", "general-purpose AI model rules"), ("2026-08-02", "transparency (Article 50), enforcement starts"), ("2026-12-02", "new prohibition 9, Article 50(2) transition ends"), ("2027-12-02", "high-risk, Annex III areas"), ("2028-08-02", "high-risk inside regulated products, Annex I")]
for day, what in DATES:
    print(day, what)
print("source:", SOURCE)
