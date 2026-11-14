import copy

from _card import build_card, lint_card, config_digest

draft = copy.deepcopy(build_card())
draft["limitations"] = ["none", "Model may be wrong"]
draft["evaluation"][0].pop("dataset")
draft["evaluation"][1]["label"] = "measured"
draft["data_sources"][1].pop("license")
del draft["out_of_scope"]

for issue in lint_card(draft, current_digest=config_digest()):
    print("-", issue)
