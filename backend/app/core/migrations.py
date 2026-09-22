"""Run Alembic `upgrade head` on API startup."""

from pathlib import Path

from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    """Apply Alembic migrations to `head` (API startup)."""
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
