PLATFORMS = {
    "Amazon Bedrock": {
        "residency": {"geographic profile (US, EU, APAC)", "global profile"},
        "auth": "IAM roles and policies",
        "api": "Converse API (one shape for many models)",
    },
    "Google Vertex AI": {
        "residency": {"regional endpoint", "multi-region endpoint (us, eu)", "global endpoint"},
        "auth": "Google service accounts and IAM",
        "api": "generateContent",
    },
    "Azure OpenAI (Foundry Models)": {
        "residency": {"Global", "Data Zone (US, EU, APAC)", "Standard (Azure geography)"},
        "auth": "API key or Microsoft Entra ID",
        "api": "OpenAI v1 API with the resource base_url",
    },
}
STRICT = {"geographic profile (US, EU, APAC)", "regional endpoint", "multi-region endpoint (us, eu)", "Data Zone (US, EU, APAC)", "Standard (Azure geography)"}

SCENARIOS = {
    "A. public FAQ chat, no personal data": dict(needs_boundary=False, cloud_team=False),
    "B. support tickets with addresses, processing must stay in one data zone": dict(needs_boundary=True, cloud_team=False),
    "C. same as B, and the company already runs everything on one cloud": dict(needs_boundary=True, cloud_team=True),
}

for title, need in SCENARIOS.items():
    print(title)
    for name, p in PLATFORMS.items():
        modes = sorted(p["residency"] & STRICT) if need["needs_boundary"] else sorted(p["residency"])
        print(f"  {name}: allowed processing modes = {modes}")
    if need["cloud_team"]:
        print("  tie-break: pick the platform of the cloud you already operate (identity, network, audit are reused)")
    elif not need["needs_boundary"]:
        print("  tie-break: pick by model quality, price and API fit; keep the adapter thin so you can switch")
    else:
        print("  tie-break: all three have a bounded mode; compare model availability in that zone")
