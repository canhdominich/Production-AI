import os
from dataclasses import dataclass


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    key_pepper: str
    demo_password: str
    primary_url: str
    secondary_url: str
    database_url: str = ""
    redis_url: str = ""
    canary_percent: int = 0
    token_ttl_s: int = 900
    breaker_cooldown_s: float = 30.0

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        missing = [k for k in ("JWT_SECRET", "KEY_PEPPER", "DEMO_PASSWORD") if not env.get(k)]
        if missing:
            raise ConfigError("missing required secrets: " + ", ".join(missing))
        if len(env["JWT_SECRET"]) < 32:
            raise ConfigError("JWT_SECRET must have at least 32 characters")
        return cls(
            jwt_secret=env["JWT_SECRET"],
            key_pepper=env["KEY_PEPPER"],
            demo_password=env["DEMO_PASSWORD"],
            primary_url=env.get("PROVIDER_PRIMARY_URL", "http://localhost:5750"),
            secondary_url=env.get("PROVIDER_SECONDARY_URL", "http://localhost:5751"),
            database_url=env.get("DATABASE_URL", ""),
            redis_url=env.get("REDIS_URL", ""),
            canary_percent=int(env.get("CANARY_PERCENT", "0")),
            token_ttl_s=int(env.get("TOKEN_TTL_S", "900")),
            breaker_cooldown_s=float(env.get("BREAKER_COOLDOWN_S", "30")),
        )
