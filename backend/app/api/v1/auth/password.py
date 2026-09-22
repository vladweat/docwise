"""Email/password register and login with host pin and SSO rules."""

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.auth._router import router
from app.api.v1.auth.common import principal_or_403, register_with_invite, register_with_org
from app.api.v1.auth.issue import issue_session
from app.core.deps import get_db
from app.core.rate_limit import enforce_auth_rate_limit
from app.core.security import verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.services.org.domains import enforce_host_pin, pinned_organization_id
from app.services.org.sso import SSO_REQUIRED
from app.services.org.tenancy import user_response


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    enforce_auth_rate_limit(request)
    email = str(body.email).strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if body.invite_token:
        principal = register_with_invite(db, body)
        if principal.organization.sso_enforced:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SSO_REQUIRED)
        enforce_host_pin(db, request, principal.organization_id, mode="register")
        db.commit()
        db.refresh(principal.user)
        issue_session(principal, response)
        return user_response(db, principal)
    pinned_id = pinned_organization_id(db, request)
    if pinned_id is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create an organization on this host")
    principal = register_with_org(db, body)
    db.commit()
    db.refresh(principal.user)
    issue_session(principal, response)
    return user_response(db, principal)


@router.post("/login", response_model=UserResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    enforce_auth_rate_limit(request)
    user = db.query(User).filter(User.email == str(body.email).strip().lower()).first()
    if user is None or user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.is_active is False:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")

    target_org_id = pinned_organization_id(db, request)
    principal = principal_or_403(db, user, target_org_id)
    enforce_host_pin(db, request, principal.organization_id, mode="login")
    issue_session(principal, response)
    return user_response(db, principal)
