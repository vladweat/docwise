"""Postgres RLS for corpus tables (`documents`, `document_chunks`)."""

from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.orm import Session

_RLS_INFO_ORG = "rls_organization_id"
_RLS_INFO_BYPASS = "rls_bypass"

# Non-superuser role so FORCE RLS applies (Postgres superusers always bypass RLS).
# Set by pytest conftest / Compose app user; empty in ad-hoc superuser shells.
_RLS_SESSION_ROLE_ENV = "DOCWISE_RLS_SESSION_ROLE"


def bind_session_rls(
    db: Session,
    *,
    organization_id: UUID | None = None,
    bypass: bool = False,
) -> None:
    """Attach tenant GUC for this SQLAlchemy session (re-applied each transaction).

    Also applies immediately when a transaction is already open — required for
    Celery ``fetch_document_for_ingestion`` (bypass → org) mid-session.
    """
    if bypass:
        db.info[_RLS_INFO_BYPASS] = True
        db.info.pop(_RLS_INFO_ORG, None)
    else:
        db.info[_RLS_INFO_BYPASS] = False
        if organization_id is not None:
            db.info[_RLS_INFO_ORG] = organization_id
        else:
            db.info.pop(_RLS_INFO_ORG, None)

    if db.in_transaction():
        _apply_rls_on_connection(db, db.connection())


def clear_session_rls(db: Session) -> None:
    """Drop tenant GUC state when returning the connection to the pool."""
    info = getattr(db, "info", None)
    if info is None:
        return
    info.pop(_RLS_INFO_ORG, None)
    info.pop(_RLS_INFO_BYPASS, None)


def _apply_session_role(connection) -> None:
    role = (os.environ.get(_RLS_SESSION_ROLE_ENV) or "").strip()
    if not role:
        return
    # Identifier only — role is created by conftest / ops, never from request input.
    if not role.replace("_", "").isalnum():
        raise RuntimeError(f"invalid {_RLS_SESSION_ROLE_ENV}={role!r}")
    connection.execute(text(f"SET LOCAL ROLE {role}"))


def _clear_rls_gucs(connection) -> None:
    connection.execute(text("SELECT set_config('app.rls_bypass', '', true)"))
    connection.execute(text("SELECT set_config('app.organization_id', '', true)"))


def _apply_rls_on_connection(session: Session, connection) -> None:
    _apply_session_role(connection)
    _clear_rls_gucs(connection)

    if session.info.get(_RLS_INFO_BYPASS):
        connection.execute(text("SET LOCAL app.rls_bypass = 'on'"))
        return

    org_id = session.info.get(_RLS_INFO_ORG)
    if org_id is not None:
        connection.execute(
            text("SELECT set_config('app.organization_id', :oid, true)"),
            {"oid": str(org_id)},
        )
        return

    # Pytest ORM fixtures (not HTTP): corpus tables need bypass or org GUC above.
    if os.environ.get("RLS_TEST_FIXTURE_BYPASS") == "1":
        connection.execute(text("SET LOCAL app.rls_bypass = 'on'"))


def register_rls_listeners() -> None:
    @event.listens_for(Session, "after_begin")
    def _rls_after_begin(session, transaction, connection):  # noqa: ARG001
        _apply_rls_on_connection(session, connection)
