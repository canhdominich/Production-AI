CONFIG = {
    "requirement": "processing must stay inside one data zone",
    "bedrock": {"routing": "global profile"},
    "azure": {"deployment_type": "Data Zone Standard"},
    "vertex": {"endpoint": "https://aiplatform.googleapis.com"},
}

BOUNDED = {
    "bedrock": lambda c: c["routing"] == "geographic profile",
    "azure": lambda c: c["deployment_type"] in ("Data Zone Standard", "Data Zone Provisioned", "Standard"),
    "vertex": lambda c: c["endpoint"].split("//")[1].split(".")[0] != "aiplatform",
}


def check(config):
    for name, ok in BOUNDED.items():
        if not ok(config[name]):
            raise ValueError(f"{name}: {config[name]} can process data anywhere; the requirement is: {config['requirement']}")


check(CONFIG)
