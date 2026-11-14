import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://anhti:anhti@localhost:5642/anhti")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:5643/0")
PROVIDER_URL = os.environ.get("PROVIDER_URL", "http://localhost:5644")
SCHEMA = os.environ.get("DB_SCHEMA", "m05_c04")
QUEUE = "m05c04:jobs"
HEARTBEAT = "m05c04:worker:heartbeat"
