from _card import build_card, lint_card, render, config_digest

card = build_card()
print(render(card))
issues = lint_card(card, current_digest=config_digest())
print()
print("sections:", len(card), "| lint issues:", len(issues))
print("config digest:", card["config_digest"])
