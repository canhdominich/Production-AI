from _genai import validate_span

good = {"name": "chat fake-small", "kind": "CLIENT", "attributes": {
    "gen_ai.operation.name": "chat", "gen_ai.provider.name": "fake", "gen_ai.request.model": "fake-small",
    "gen_ai.usage.input_tokens": 13, "gen_ai.usage.output_tokens": 60}}
cases = {
    "correct chat span": good,
    "older provider and token names": {"name": "chat fake-small", "kind": "CLIENT", "attributes": {
        "gen_ai.operation.name": "chat", "gen_ai.system": "fake", "gen_ai.usage.prompt_tokens": 13, "gen_ai.usage.completion_tokens": 60}},
    "tool span without a tool name": {"name": "execute_tool", "kind": "INTERNAL", "attributes": {
        "gen_ai.operation.name": "execute_tool"}},
    "prompt text stored without opt-in": {"name": "chat fake-small", "kind": "CLIENT", "attributes": {
        **good["attributes"], "gen_ai.input.messages": "[{...}]"}},
    "made-up attribute and wrong kind": {"name": "chat fake-small", "kind": "SERVER", "attributes": {
        **good["attributes"], "gen_ai.usage.total_tokens": 73}},
}
for title, span in cases.items():
    problems = validate_span(span)
    print(f"{title}: {'ok' if not problems else ''}")
    for p in problems:
        print("   -", p)
