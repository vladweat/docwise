"""Postgres RLS for corpus tables (`documents`, `document_chunks`)."""

from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.orm import Session

_RLS_INFO_ORG = "rls_organization_id"
_RLS_INFO_BYPASS = "rls_bypass"


def bind_session_rls(
    db: Session,
    *,
    organization_id: UUID | None = None,
    bypass: bool = False,
) -> None:
    """Attach tenant GUC for this SQLAlchemy session (re-applied each transaction)."""
    if bypass:
        db.info[_RLS_INFO_BYPASS] = True
        db.info.pop(_RLS_INFO_ORG, None)
        return
    db.info[_RLS_INFO_BYPASS] = False
    if organization_id is not None:
        db.info[_RLS_INFO_ORG] = organization_id
    else:
        db.info.pop(_RLS_INFO_ORG, None)


def clear_session_rls(db: Session) -> None:
    """Drop tenant GUC state when returning the connection to the pool."""
    db.info.pop(_RLS_INFO_ORG, None)
    db.info.pop(_RLS_INFO_BYPASS, None)


def _apply_rls_on_connection(session: Session, connection) -> None:
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
