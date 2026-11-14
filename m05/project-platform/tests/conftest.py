import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from anhti_platform.api import create_app  # noqa: E402
from anhti_platform.base import GatewayRequest, ProviderError, ProviderResult, estimate_prompt_tokens  # noqa: E402
from anhti_platform.config import Settings  # noqa: E402
from anhti_platform.telemetry import Telemetry  # noqa: E402
from anhti_platform.usage import MemoryUsageStore  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc).timestamp()
PASSWORD = "demo-pass-2026"


class Clock:
    def __init__(self, t=NOW):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class ScriptedProvider:
    def __init__(self, name, script=()):
        self.name = name
        self.script = list(script)
        self.calls = 0

    def complete(self, model, messages, max_tokens=None, request_id=None, output_tokens=None, timeout_s=None):
        self.calls += 1
        step = self.script.pop(0) if self.script else "ok"
        if step != "ok":
            kind, _, code = step.partition(":")
            raise ProviderError(kind, int(code) if code else None, 1.5 if kind == "rate_limit" else None)
        return ProviderResult("Don hang cua ban dang tren duong giao.", estimate_prompt_tokens(messages), 40, 0.1, 0.2)


def settings():
    return Settings(jwt_secret="unit-test-secret-" + "k" * 24, key_pepper="unit-test-pepper", demo_password=PASSWORD,
                    primary_url="http://primary.invalid", secondary_url="http://secondary.invalid")


def seed_spend(store, tenant_id, usd, ts=NOW):
    store.add({"request_id": "seed", "ts": ts, "tenant_id": tenant_id, "user_id": "seed", "feature": "chat", "model": "fake-medium",
              "provider": "primary", "status": "ok", "prompt_tokens": 0, "output_tokens": 0, "cost_usd": usd, "latency_ms": 1.0,
              "attempts": 1, "fallback_used": False, "prompt_version": "v1"})


class World:
    def __init__(self, primary_script=(), secondary_script=()):
        self.clock = Clock()
        self.sleeps = []
        self.primary = ScriptedProvider("primary", primary_script)
        self.secondary = ScriptedProvider("secondary", secondary_script)
        self.store = MemoryUsageStore()
        self.telemetry = Telemetry()
        self.app = create_app(settings(), [self.primary, self.secondary], store=self.store, telemetry=self.telemetry,
                              clock=self.clock, sleep=self.sleeps.append)
        self.http = TestClient(self.app)

    def login(self, user_id):
        r = self.http.post("/auth/token", json={"user_id": user_id, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"authorization": "Bearer " + r.json()["access_token"]}

    def chat(self, user_id, message="don at047838 bao gio toi", feature="chat", **extra):
        return self.http.post("/v1/chat", json={"message": message, "feature": feature, **extra}, headers=self.login(user_id))


@pytest.fixture
def world():
    return World()


@pytest.fixture
def make_world():
    return World
