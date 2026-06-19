from __future__ import annotations

from pathlib import Path

import yaml


APP_ROOT = Path(__file__).resolve().parents[1]
CHART_ROOT = APP_ROOT / "helm" / "platform"


def test_helm_db_secret_rejects_missing_or_weak_password_defaults() -> None:
    template = (CHART_ROOT / "templates" / "secret-db.yaml").read_text(encoding="utf-8")

    assert 'default "changeme"' not in template
    assert "fail $weakPasswordMsg" in template
    assert '(eq $dbPassword "changeme")' in template
    assert '(eq $dbPassword "postgres")' in template


def test_helm_values_do_not_ship_db_password_defaults() -> None:
    values = yaml.safe_load((CHART_ROOT / "values.yaml").read_text(encoding="utf-8"))

    assert values["db"]["password"] == ""
    assert values["postgres"]["password"] == ""


def test_bundled_postgres_template_rejects_weak_password_defaults() -> None:
    template = (CHART_ROOT / "templates" / "postgres.yaml").read_text(encoding="utf-8")

    assert "value: {{ .Values.postgres.password | quote }}" not in template
    assert "postgres.password must be set to a non-default value" in template
    assert '(eq $postgresPassword "postgres")' in template


def test_docker_compose_requires_operator_supplied_postgres_password() -> None:
    compose = yaml.safe_load((APP_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    postgres_env = compose["services"]["postgres"]["environment"]
    api_env = compose["services"]["api"]["environment"]

    assert postgres_env["POSTGRES_PASSWORD"].startswith("${POSTGRES_PASSWORD:?")
    assert "postgres:postgres" not in api_env["DATABASE_URL"]
    assert "${POSTGRES_PASSWORD:?" in api_env["DATABASE_URL"]
