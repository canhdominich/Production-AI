import pytest

from anhti_platform.auth import ApiKeyStore, AuthError, hash_api_key, issue_token, verify_token
from anhti_platform.base import TenantRegistry
from anhti_platform.config import ConfigError, Settings
from conftest import NOW, PASSWORD, settings


def test_login_gives_a_token_that_carries_tenant_and_role(world):
    r = world.http.post("/auth/token", json={"user_id": "dp-03", "password": PASSWORD})
    assert r.status_code == 200
    p = verify_token(settings().jwt_secret, r.json()["access_token"], NOW)
    assert (p.tenant_id, p.user_id, p.role, p.kind) == ("br-dau-pho", "dp-03", "branch_manager", "user")


def test_wrong_password_is_401(world):
    assert world.http.post("/auth/token", json={"user_id": "dp-03", "password": "nope"}).status_code == 401


def test_expired_token_is_rejected():
    token = issue_token(settings().jwt_secret, "br-dau-pho", "dp-01", "cskh_agent", NOW, ttl=900)
    with pytest.raises(AuthError):
        verify_token(settings().jwt_secret, token, NOW + 901)


def test_token_signed_with_another_secret_is_rejected():
    token = issue_token("another-secret-" + "z" * 24, "br-dau-pho", "dp-01", "cskh_agent", NOW)
    with pytest.raises(AuthError):
        verify_token(settings().jwt_secret, token, NOW)


def test_unsigned_token_is_rejected():
    import jwt
    forged = jwt.encode({"iss": "anhti-platform", "aud": "anhti-api", "sub": "dp-03", "tid": "br-dau-pho", "role": "branch_manager",
                         "exp": int(NOW) + 900}, key=None, algorithm="none")
    with pytest.raises(AuthError):
        verify_token(settings().jwt_secret, forged, NOW)


def test_valid_signature_but_unknown_user_is_rejected(world):
    token = issue_token(settings().jwt_secret, "br-dau-pho", "dp-99", "branch_manager", NOW)
    r = world.http.get("/v1/usage", headers={"authorization": "Bearer " + token})
    assert r.status_code == 401


def test_role_in_token_must_match_the_directory(world):
    token = issue_token(settings().jwt_secret, "br-dau-pho", "dp-01", "branch_manager", NOW)
    assert world.http.get("/v1/usage", headers={"authorization": "Bearer " + token}).status_code == 401


def test_api_key_authenticates_an_integration(world):
    r = world.http.post("/v1/chat", json={"message": "gio giao du kien"}, headers={"x-api-key": "demo-key-cau-go"})
    assert r.status_code == 200
    assert world.store.events[-1]["tenant_id"] == "br-cau-go"


def test_unknown_api_key_is_401(world):
    r = world.http.post("/v1/chat", json={"message": "hi"}, headers={"x-api-key": "demo-key-nope"})
    assert r.status_code == 401


def test_api_keys_are_kept_as_hashes():
    store = ApiKeyStore(TenantRegistry(), "pepper")
    assert "demo-key-cau-go" not in str(store._hashes)
    assert hash_api_key("demo-key-cau-go", "pepper") in store._hashes
    assert hash_api_key("demo-key-cau-go", "other") not in store._hashes


def test_missing_credentials_is_401_with_challenge(world):
    r = world.http.post("/v1/chat", json={"message": "hi"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_error_body_does_not_explain_why_authentication_failed(world):
    bad_key = world.http.post("/v1/chat", json={"message": "hi"}, headers={"x-api-key": "x"}).json()
    no_creds = world.http.post("/v1/chat", json={"message": "hi"}).json()
    assert bad_key == no_creds


def test_agent_cannot_use_the_knowledge_assistant(world):
    assert world.chat("dp-01", feature="knowledge_assistant").status_code == 403
    assert world.chat("dp-02", feature="knowledge_assistant").status_code == 200


def test_branch_without_the_weekly_report_cannot_get_it_even_as_lead(world):
    assert world.chat("bs-02", feature="weekly_report_agent").status_code == 403
    assert world.chat("dp-03", feature="weekly_report_agent").status_code == 200


def test_body_cannot_name_another_tenant(world):
    r = world.http.post("/v1/chat", json={"message": "hi", "tenant_id": "br-khu-cong-nghiep"}, headers=world.login("dp-01"))
    assert r.status_code == 422


def test_usage_of_another_tenant_looks_like_a_missing_one(world):
    h = world.login("dp-03")
    other = world.http.get("/v1/usage/br-khu-cong-nghiep", headers=h)
    missing = world.http.get("/v1/usage/br-does-not-exist", headers=h)
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()


def test_only_managers_read_usage(world):
    assert world.http.get("/v1/usage", headers=world.login("dp-02")).status_code == 403
    assert world.http.get("/v1/usage", headers=world.login("dp-03")).status_code == 200


def test_usage_shows_only_the_callers_tenant(world):
    world.chat("dp-02")
    world.chat("dp-02")
    world.chat("kc-02")
    mine = world.http.get("/v1/usage", headers=world.login("dp-03")).json()
    theirs = world.http.get("/v1/usage", headers=world.login("kc-03")).json()
    assert (mine["tenant_id"], mine["requests"]) == ("br-dau-pho", 2)
    assert (theirs["tenant_id"], theirs["requests"]) == ("br-khu-cong-nghiep", 1)


def test_rate_limit_is_per_tenant(world):
    codes = [world.chat("bs-01").status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429
    assert world.chat("dp-01").status_code == 200


def test_rate_limited_answer_says_when_to_retry(world):
    for _ in range(30):
        world.chat("bs-01")
    r = world.chat("bs-01")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    world.clock.advance(61)
    assert world.chat("bs-01").status_code == 200


def test_rate_limited_calls_never_reach_the_provider(world):
    for _ in range(30):
        world.chat("bs-01")
    before = world.primary.calls
    world.chat("bs-01")
    assert world.primary.calls == before


def test_settings_refuse_to_start_without_secrets():
    with pytest.raises(ConfigError):
        Settings.from_env({"KEY_PEPPER": "p", "DEMO_PASSWORD": "d"})
    with pytest.raises(ConfigError):
        Settings.from_env({"JWT_SECRET": "short", "KEY_PEPPER": "p", "DEMO_PASSWORD": "d"})
    ok = Settings.from_env({"JWT_SECRET": "s" * 32, "KEY_PEPPER": "p", "DEMO_PASSWORD": "d"})
    assert ok.canary_percent == 0
