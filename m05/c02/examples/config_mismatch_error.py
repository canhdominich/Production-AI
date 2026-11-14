import os

import openai

import _paths  # noqa: F401
from _chat_client import ChatClient

os.environ["CHAT_PROFILE"] = "ollama"
os.environ["CHAT_BASE_URL"] = "http://localhost:11434"
try:
    ChatClient().ask("Xin chào")
except openai.NotFoundError as e:
    print("missing /v1 in base_url:", str(e))

os.environ["CHAT_BASE_URL"] = "http://localhost:11434/v1"
os.environ["CHAT_MODEL"] = "fake-small"
ChatClient().ask("Xin chào")
