from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.auth._router import router
from app.api.v1.auth.issue import issue_session
from app.core.auth_cookies import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    decode_refresh_token,
    revoke_refresh_token,
)
from app.core.deps import get_current_user, get_db
from app.core.rls import bind_session_rls
from app.core.errors import AppError
from app.core.principal import Principal
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User
from app.schemas.auth import SwitchOrganizationRequest
from app.schemas.user import UserResponse
from app.services.org.domains import enforce_host_pin
from app.services.org.sso import SSO_REQUIRED, has_sso_fresh, session_allowed_for_org
from app.services.org.tenancy import get_membership, principal_from_parts, resolve_principal, user_response


@router.post("/refresh", response_model=UserResponse)
def refresh_session(request: Request, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_refresh_token(raw)
        email = payload.get("sub")
        org_raw = payload.get("org_id")
        org_id = UUID(str(org_raw)) if org_raw else None
    except (ValueError, TypeError):
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        revoke_refresh_token(raw)
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    principal = resolve_principal(db, user, org_id)
    sso_claim = payload.get("sso") is True
    if principal is None or not session_allowed_for_org(principal.organization, sso_claim=sso_claim):
        revoke_refresh_token(raw)
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        enforce_host_pin(db, request, principal.organization_id, mode="session")
    except (HTTPException, AppError):
        revoke_refresh_token(raw)
        clear_auth_cookies(response)
        raise

    bind_session_rls(db, organization_id=principal.organization_id)
    revoke_refresh_token(raw)
    issue_session(principal, response, sso=sso_claim)
    return user_response(db, principal)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        revoke_refresh_token(raw)
    clear_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
def me(
    current_user: Principal = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    return user_response(db, current_user)


@router.post("/switch-organization", response_model=UserResponse)
def switch_organization(
    body: SwitchOrganizationRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(get_current_user),
) -> UserResponse:
    membership = get_membership(db, current_user.id, body.organization_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    organization = db.get(Organization, membership.organization_id)
    if organization is None or organization.status != OrganizationStatus.active.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    enforce_host_pin(db, request, organization.id, mode="switch")
    if organization.sso_enforced and not has_sso_fresh(current_user.id, organization.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SSO_REQUIRED)
    principal = principal_from_parts(current_user.user, membership, organization)
    bind_session_rls(db, organization_id=principal.organization_id)
    issue_session(principal, response, sso=organization.sso_enforced)
    return user_response(db, principal)
