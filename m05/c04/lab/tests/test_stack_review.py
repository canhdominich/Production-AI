from pathlib import Path

import pytest

import stack_review as sr

GOOD_DOCKERFILE = """
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
RUN useradd --system --uid 10001 app
COPY --from=builder /app/.venv /app/.venv
COPY app /app/app
USER app
CMD ["uvicorn", "app.api:app"]
"""

GOOD_COMPOSE = """
services:
  postgres:
    image: pgvector/pgvector:pg17
    restart: unless-stopped
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-demo}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5642:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U anhti"]
  migrate:
    image: demo-app:1
    restart: "no"
    depends_on:
      postgres:
        condition: service_healthy
  api:
    build: .
    image: demo-app:1
    restart: unless-stopped
    ports:
      - "127.0.0.1:5641:8000"
    healthcheck:
      test: ["CMD", "true"]
    depends_on:
      migrate:
        condition: service_completed_successfully
volumes:
  pgdata:
"""


def test_parse_dockerfile_stages():
    stages = sr.parse_dockerfile(GOOD_DOCKERFILE)
    assert [s["name"] for s in stages] == ["builder", "runtime"]
    assert stages[0]["base"] == "python:3.12-slim"
    assert ("RUN", "uv sync --frozen --no-dev") in stages[0]["instructions"]
    assert stages[1]["instructions"][-1][0] == "CMD"


def test_parse_dockerfile_joins_continuation_lines_and_skips_comments():
    text = "# comment\nFROM python:3.12-slim\nRUN apt-get update && \\\n    apt-get install -y curl\n"
    stages = sr.parse_dockerfile(text)
    assert stages[0]["name"] == ""
    assert stages[0]["instructions"] == [("RUN", "apt-get update &&  apt-get install -y curl")]


def test_good_dockerfile_has_no_problems():
    assert sr.check_dockerfile(GOOD_DOCKERFILE) == []


def test_single_stage_is_reported():
    text = "FROM python:3.12-slim\nCOPY pyproject.toml uv.lock ./\nRUN uv sync\nUSER app\n"
    assert any("single stage" in e for e in sr.check_dockerfile(text))


def test_latest_and_untagged_bases_are_reported():
    text = GOOD_DOCKERFILE.replace("FROM python:3.12-slim AS builder", "FROM python:latest AS builder").replace("AS runtime", "AS runtime").replace("FROM python:3.12-slim AS runtime", "FROM python AS runtime")
    errs = sr.check_dockerfile(text)
    assert any("python:latest" in e for e in errs)
    assert any("not pinned" in e and e.endswith("python") for e in errs)


def test_stage_names_as_base_are_not_unpinned():
    text = GOOD_DOCKERFILE + "\nFROM runtime AS test\nUSER app\n"
    assert not any("not pinned" in e for e in sr.check_dockerfile(text))


def test_code_before_install_is_reported():
    text = GOOD_DOCKERFILE.replace("COPY pyproject.toml uv.lock ./", "COPY . /app")
    errs = sr.check_dockerfile(text)
    assert any("before dependencies" in e and "builder" in e for e in errs)


def test_dependency_files_before_install_are_fine():
    text = GOOD_DOCKERFILE.replace("COPY pyproject.toml uv.lock ./", "COPY --chown=1000 pyproject.toml uv.lock ./")
    assert sr.check_dockerfile(text) == []


def test_root_final_stage_is_reported():
    assert any("root" in e for e in sr.check_dockerfile(GOOD_DOCKERFILE.replace("USER app\n", "")))
    assert any("root" in e for e in sr.check_dockerfile(GOOD_DOCKERFILE.replace("USER app", "USER root")))


def test_parse_compose_normalises_depends_on():
    cfg = sr.parse_compose(GOOD_COMPOSE)
    assert set(cfg["services"]) == {"postgres", "migrate", "api"}
    assert cfg["services"]["migrate"]["depends_on"] == {"postgres": "service_healthy"}
    assert cfg["services"]["api"]["healthcheck"] is True
    assert cfg["volumes"] == ["pgdata"]
    assert cfg["services"]["postgres"]["restart"] == "unless-stopped"
    listed = sr.parse_compose("services:\n  a:\n    image: x:1\n    depends_on: [b]\n  b:\n    image: y:1\n")
    assert listed["services"]["a"]["depends_on"] == {"b": "service_started"}
    assert listed["services"]["a"]["restart"] == ""


def test_good_compose_has_no_problems():
    assert sr.check_compose(GOOD_COMPOSE) == []


def test_missing_healthcheck_is_reported():
    text = GOOD_COMPOSE.replace('    healthcheck:\n      test: ["CMD", "true"]\n', "")
    assert "api: long-running service has no healthcheck" in sr.check_compose(text)


def test_wrong_depends_on_condition_is_reported():
    text = GOOD_COMPOSE.replace("condition: service_healthy", "condition: service_started")
    assert "migrate: depends_on postgres needs condition service_healthy, found service_started" in sr.check_compose(text)
    text = GOOD_COMPOSE.replace("condition: service_completed_successfully", "condition: service_healthy")
    assert "api: depends_on migrate needs condition service_completed_successfully, found service_healthy" in sr.check_compose(text)


def test_image_ports_volume_and_secret_rules():
    text = (GOOD_COMPOSE.replace("pgvector/pgvector:pg17", "pgvector/pgvector:latest")
            .replace('"127.0.0.1:5642:5432"', '"5432:5432"')
            .replace("${POSTGRES_PASSWORD:-demo}", "demo")
            .replace("      - pgdata:/var/lib/postgresql/data\n", ""))
    errs = sr.check_compose(text)
    assert "postgres: image not pinned to a tag: pgvector/pgvector:latest" in errs
    assert "postgres: published port 5432:5432 is not bound to 127.0.0.1" in errs
    assert "postgres: database data is not on a named volume" in errs
    assert "postgres: secret POSTGRES_PASSWORD written in the file, read it from the environment" in errs


def test_default_host_port_is_reported_and_errors_are_sorted():
    errs = sr.check_compose(GOOD_COMPOSE.replace("127.0.0.1:5642:5432", "127.0.0.1:5432:5432"))
    assert errs == ["postgres: host port 5432 is a default port, use a project port"]
    many = sr.check_compose(GOOD_COMPOSE.replace('    healthcheck:\n      test: ["CMD", "true"]\n', "").replace("127.0.0.1:5641:8000", "8000:8000"))
    assert many == sorted(many) and len(many) == len(set(many))


@pytest.mark.parametrize("size_mb, hosts, air_gapped, expected", [
    (90, 3, False, "bake"),
    (149, 1, False, "bake"),
    (150, 1, False, "volume"),
    (4000, 1, False, "volume"),
    (4000, 3, False, "mirror"),
    (4000, 3, True, "bake"),
])
def test_weights_strategy(size_mb, hosts, air_gapped, expected):
    assert sr.weights_strategy(size_mb, hosts, air_gapped) == expected


def test_review_reports_missing_files(tmp_path):
    lines = sr.review(tmp_path)
    assert lines == ["Dockerfile: 1 problem(s)", "  - Dockerfile missing", "compose.yaml: 1 problem(s)", "  - compose.yaml missing"]
    (tmp_path / "Dockerfile").write_text(GOOD_DOCKERFILE)
    (tmp_path / "compose.yaml").write_text(GOOD_COMPOSE)
    assert sr.review(tmp_path) == ["Dockerfile: ok", "compose.yaml: ok"]
