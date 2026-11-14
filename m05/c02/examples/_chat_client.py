import json
import os
import time
from pathlib import Path

from openai import OpenAI

CONFIG = Path(__file__).with_name("endpoints.json")


class ChatClient:
    def __init__(self, profile=None, timeout=120, max_retries=0):
        self.profile = profile or os.environ.get("CHAT_PROFILE", "ollama")
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))[self.profile]
        self.base_url = os.environ.get("CHAT_BASE_URL", cfg["base_url"])
        self.model = os.environ.get("CHAT_MODEL", cfg["model"])
        self.extra = cfg["extra"]
        self.http = OpenAI(base_url=self.base_url, api_key=os.environ.get("CHAT_API_KEY", cfg["api_key"]), timeout=timeout, max_retries=max_retries)

    def ask(self, question, max_tokens=120):
        t0 = time.perf_counter()
        r = self.http.chat.completions.create(model=self.model, max_tokens=max_tokens, temperature=0, seed=7,
                                              messages=[{"role": "user", "content": question}], **self.extra)
        return {"text": r.choices[0].message.content or "", "finish": r.choices[0].finish_reason,
                "tokens_in": r.usage.prompt_tokens, "tokens_out": r.usage.completion_tokens, "seconds": time.perf_counter() - t0}
