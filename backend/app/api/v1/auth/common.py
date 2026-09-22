"""Auth handler helpers (principal resolution, error mapping)."""

from uuid import UUID

from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.core.security import hash_password
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest
from app.services.org.sso import SSO_REQUIRED
from app.services.org.tenancy import (
    accept_invite,
    add_membership,
    create_organization,
    first_membership,
    get_membership,
    get_pending_invite,
    principal_from_parts,
    resolve_principal,
    resolve_principal_for_password,
)

_NO_MEMBERSHIP = "No organization membership"


def verify_google_id_token(token: str, client_id: str) -> dict:
    return id_token.verify_oauth2_token(token, google_requests.Request(), client_id)


def principal_or_403(
    db: Session,
    user: User,
    organization_id: UUID | None,
    *,
    from_sso: bool = False,
) -> Principal:
    if from_sso:
        principal = resolve_principal(db, user, organization_id)
    else:
        principal = resolve_principal_for_password(db, user, organization_id)
    if principal is None:
        membership = (
            get_membership(db, user.id, organization_id)
            if organization_id is not None
            else first_membership(db, user.id)
        )
        if membership is not None:
            org = db.get(Organization, membership.organization_id)
            if org is not None and org.status == OrganizationStatus.suspended.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Organization is suspended",
                )
            if org is not None and org.sso_enforced and not from_sso:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SSO_REQUIRED)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_NO_MEMBERSHIP)
    return principal


def register_with_invite(db: Session, body: RegisterRequest) -> Principal:
    invite = get_pending_invite(db, body.invite_token or "")
    if invite.email != str(body.email).strip().lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invite email mismatch")
    user = User(
        email=str(body.email).strip().lower(),
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.flush()
    membership = accept_invite(db, invite, user)
    organization = db.get(Organization, membership.organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return principal_from_parts(user, membership, organization)


def register_with_org(db: Session, body: RegisterRequest) -> Principal:
    user = User(
        email=str(body.email).strip().lower(),
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.flush()
    organization = create_organization(db, body.organization_name or "")
    membership = add_membership(
        db,
        organization=organization,
        user=user,
        role=UserRole.admin.value,
    )
    return principal_from_parts(user, membership, organization)
