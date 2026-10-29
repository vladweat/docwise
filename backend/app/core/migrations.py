"""Alembic upgrade helper used by the one-shot Compose migration job."""

from pathlib import Path

from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    """Apply Alembic migrations to `head`."""
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
