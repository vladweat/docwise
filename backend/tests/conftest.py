"""Route pytest at `docwise_test` so fixtures never wipe the dev database.

Must run before any test module imports `app.core.database` / `app.main`.
"""

from __future__ import annotations

import os
import time
from urllib.parse import urlparse, urlunparse

import pytest

TEST_DB_NAME = "docwise_test"

_ORIGINAL_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://docwise:change_this_in_prod@postgres:5432/docwise_db",
)


def _with_db_name(url: str, name: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{name}"))


def _database_name(url: str) -> str:
    return urlparse(url).path.lstrip("/").split("?")[0]


os.environ["DATABASE_URL"] = _with_db_name(_ORIGINAL_DATABASE_URL, TEST_DB_NAME)
os.environ["COOKIE_SAMESITE"] = "lax"
os.environ["COOKIE_SECURE"] = "false"
os.environ["RATE_LIMIT_AUTH_PER_MINUTE"] = "0"
os.environ["RATE_LIMIT_UPLOAD_PER_MINUTE"] = "0"
os.environ["RATE_LIMIT_CHAT_PER_MINUTE"] = "0"
os.environ["PLAN_STARTER_SEATS"] = "1000"
os.environ["PLAN_STARTER_PAGES"] = "1000000"
os.environ["PLAN_STARTER_TOKENS"] = "100000000"
os.environ["PLAN_TEAM_SEATS"] = "1000"
os.environ["PLAN_TEAM_PAGES"] = "1000000"
os.environ["PLAN_TEAM_TOKENS"] = "100000000"
os.environ["PLAN_ENTERPRISE_SEATS"] = "1000"
os.environ["PLAN_ENTERPRISE_PAGES"] = "1000000"
os.environ["PLAN_ENTERPRISE_TOKENS"] = "100000000"
os.environ["BILLING_PROVIDER"] = "dev"
os.environ["SSO_PROVIDER"] = "dev"
os.environ["STRIPE_SECRET_KEY"] = ""
os.environ["STRIPE_WEBHOOK_SECRET"] = ""
os.environ["RLS_TEST_FIXTURE_BYPASS"] = "1"


def _ensure_test_database() -> None:
    from sqlalchemy import create_engine, text

    admin_engine = create_engine(_ORIGINAL_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DB_NAME},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        admin_engine.dispose()


def _test_db_revision() -> str | None:
    from sqlalchemy import create_engine

    from alembic.runtime.migration import MigrationContext

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            return context.get_current_revision()
    finally:
        engine.dispose()


def _alembic_head_revision() -> str:
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    if head is None:
        raise RuntimeError("Alembic has no head revision")
    return head


def _run_migrations_if_needed() -> None:
    from app.core.config import get_settings
    from app.core.migrations import run_migrations

    get_settings.cache_clear()
    head = _alembic_head_revision()
    current = _test_db_revision()
    if current == head:
        print(f"pytest: {TEST_DB_NAME} schema at head ({head[:12]}…)", flush=True)
        return
    print(f"pytest: migrating {TEST_DB_NAME} ({current or 'empty'} → {head[:12]}…)", flush=True)
    run_migrations()
    print("pytest: migrations done", flush=True)


_PREP_START = time.perf_counter()
_ensure_test_database()
_run_migrations_if_needed()
_PREP_SECONDS = time.perf_counter() - _PREP_START


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def pytest_report_header(config):  # noqa: ARG001
    return [
        f"docwise_test ready in {_PREP_SECONDS:.1f}s (Alembic checked; suite is ~246 HTTP/DB tests)",
    ]


def pytest_sessionstart() -> None:
    db_name = _database_name(os.environ.get("DATABASE_URL", ""))
    if db_name != TEST_DB_NAME:
        raise RuntimeError(
            f"Refusing to run tests against database {db_name!r}; expected {TEST_DB_NAME!r}."
        )
