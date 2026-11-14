import openai

import _paths  # noqa: F401
from _chat_client import ChatClient
from _harness import provider

QUESTION = "Đơn AT123456 giao trễ thì khách được báo trước bao lâu? Trả lời một câu."


def show(profile, label):
    client = ChatClient(profile)
    try:
        a = client.ask(QUESTION)
    except openai.APIConnectionError:
        print(f"{label:<9} {client.base_url:<28} {client.model:<14} no server listening (expected, vLLM needs a GPU host)")
        return
    print(f"{label:<9} {client.base_url:<28} {client.model:<14} in={a['tokens_in']:>3} out={a['tokens_out']:>3} finish={a['finish']:<6} {a['seconds']:5.1f}s  {a['text'][:42]!r}")


with provider(5620, seed=42, time_scale=0.05):
    for name, label in (("fake", "fake"), ("ollama", "ollama 1"), ("ollama", "ollama 2"), ("vllm", "vllm")):
        show(name, label)
