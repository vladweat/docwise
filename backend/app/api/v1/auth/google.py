"""Google OAuth login and registration (session org from membership)."""

import logging

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.auth._router import router
from app.api.v1.auth.common import principal_or_403
from app.api.v1.auth.issue import issue_session
from app.core.config import get_settings
from app.core.deps import get_db
from app.core.rate_limit import enforce_auth_rate_limit
from app.models.user import User, UserRole
from app.schemas.auth import GoogleAuthRequest
from app.schemas.user import UserResponse
from app.services.org.domains import enforce_host_pin, pinned_organization_id
from app.services.org.tenancy import (
    accept_invite,
    add_membership,
    create_organization,
    get_pending_invite,
    user_response,
)

logger = logging.getLogger(__name__)


@router.post("/google", response_model=UserResponse)
def google_auth(
    body: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    enforce_auth_rate_limit(request)
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    try:
        from app.api.v1 import auth as auth_pkg

        idinfo = auth_pkg.verify_google_id_token(body.id_token, settings.google_client_id)
    except ValueError as exc:
        logger.warning("Google token verification failed error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
        ) from exc

    google_sub: str | None = idinfo.get("sub")
    email: str | None = idinfo.get("email")
    if not google_sub or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token missing required claims",
        )
    if idinfo.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email is not verified",
        )
    email = email.strip().lower()

    user = db.query(User).filter(User.google_id == google_sub).first()
    created = False
    if user is None:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            if user.google_id and user.google_id != google_sub:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email linked to a different Google account",
                )
            user.google_id = google_sub
        else:
            user = User(email=email, google_id=google_sub)
            db.add(user)
            db.flush()
            created = True

    if user.is_active is False:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")

    invite_token = (body.invite_token or "").strip()
    org_name = (body.organization_name or "").strip()
    target_org_id = None
    pinned_id = pinned_organization_id(db, request)
    if invite_token:
        invite = get_pending_invite(db, invite_token)
        if pinned_id is not None and pinned_id != invite.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create an organization on this host",
            )
        membership = accept_invite(db, invite, user)
        target_org_id = membership.organization_id
    elif created:
        if pinned_id is not None:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create an organization on this host",
            )
        if not org_name:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="organization_name is required",
            )
        organization = create_organization(db, org_name)
        add_membership(db, organization=organization, user=user, role=UserRole.admin.value)
        target_org_id = organization.id

    db.commit()
    db.refresh(user)
    if target_org_id is None:
        target_org_id = pinned_id
    principal = principal_or_403(db, user, target_org_id)
    enforce_host_pin(db, request, principal.organization_id, mode="login")
    issue_session(principal, response)
    return user_response(db, principal)
