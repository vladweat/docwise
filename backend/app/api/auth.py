import logging
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.core.auth_cookies import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    create_refresh_token,
    decode_refresh_token,
    revoke_refresh_token,
    set_auth_cookies,
)
from app.core.config import get_settings
from app.core.csrf import CSRF_HEADER_VALUE
from app.core.deps import get_current_user, get_db
from app.core.principal import Principal
from app.core.security import create_access_token, hash_password, verify_password
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User, UserRole
from app.schemas.auth import GoogleAuthRequest, LoginRequest, RegisterRequest, SwitchOrganizationRequest
from app.schemas.sso import DevSsoAssertion
from app.schemas.user import UserResponse
from app.services.domains import (
    enforce_host_pin,
    pinned_organization_id,
)
from app.services.sso import (
    SSO_NOT_FOUND,
    SSO_REQUIRED,
    complete_sso_login,
    has_sso_fresh,
    mark_sso_fresh,
    public_sso_target,
    session_allowed_for_org,
)
from app.services.tenancy import (
    accept_invite,
    add_membership,
    create_organization,
    first_membership,
    get_membership,
    get_pending_invite,
    principal_from_parts,
    resolve_principal,
    resolve_principal_for_password,
    user_response,
)
from app.utils.rate_limit import client_ip, enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_NO_MEMBERSHIP = "No organization membership"


def verify_google_id_token(token: str, client_id: str) -> dict:
    return id_token.verify_oauth2_token(token, google_requests.Request(), client_id)


def _auth_rate_limit(request: Request) -> None:
    settings = get_settings()
    enforce_rate_limit("auth", client_ip(request), settings.rate_limit_auth_per_minute)


def _issue_session(principal: Principal, response: Response, *, sso: bool = False) -> Principal:
    org_id = str(principal.organization_id)
    access = create_access_token(principal.email, role=principal.role, org_id=org_id, sso=sso)
    refresh = create_refresh_token(principal.email, role=principal.role, org_id=org_id, sso=sso)
    set_auth_cookies(response, access_token=access, refresh_token=refresh)
    if sso:
        mark_sso_fresh(principal.id, principal.organization_id)
    return principal


def _principal_or_403(
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


def _register_with_invite(db: Session, body: RegisterRequest) -> Principal:
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


def _register_with_org(db: Session, body: RegisterRequest) -> Principal:
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


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    _auth_rate_limit(request)
    email = str(body.email).strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if body.invite_token:
        principal = _register_with_invite(db, body)
        if principal.organization.sso_enforced:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SSO_REQUIRED)
        enforce_host_pin(db, request, principal.organization_id, mode="register")
        db.commit()
        db.refresh(principal.user)
        _issue_session(principal, response)
        return user_response(db, principal)
    pinned_id = pinned_organization_id(db, request)
    if pinned_id is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create an organization on this host")
    principal = _register_with_org(db, body)
    db.commit()
    db.refresh(principal.user)
    _issue_session(principal, response)
    return user_response(db, principal)


@router.post("/login", response_model=UserResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    _auth_rate_limit(request)
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
    principal = _principal_or_403(db, user, target_org_id)
    enforce_host_pin(db, request, principal.organization_id, mode="login")
    _issue_session(principal, response)
    return user_response(db, principal)


@router.post("/google", response_model=UserResponse)
def google_auth(
    body: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    _auth_rate_limit(request)
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    try:
        idinfo = verify_google_id_token(body.id_token, settings.google_client_id)
    except ValueError as exc:
        logger.warning("Google token verification failed: %s", exc)
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
    principal = _principal_or_403(db, user, target_org_id)
    enforce_host_pin(db, request, principal.organization_id, mode="login")
    _issue_session(principal, response)
    return user_response(db, principal)


def _sso_json_response(request: Request) -> bool:
    header = (request.headers.get("x-requested-with") or "").strip()
    if header == CSRF_HEADER_VALUE:
        return True
    accept = (request.headers.get("accept") or "").lower()
    return "application/json" in accept and "text/html" not in accept


@router.get("/sso/{slug}/login")
def sso_login(slug: str, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    _auth_rate_limit(request)
    target = public_sso_target(db, slug)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SSO_NOT_FOUND)
    organization, _connection = target
    pinned_id = pinned_organization_id(db, request)
    if pinned_id is not None and pinned_id != organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SSO_NOT_FOUND)
    settings = get_settings()
    if settings.sso_provider_name != "dev":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SSO_NOT_FOUND)
    location = f"{settings.public_frontend_url()}/login?sso={quote(organization.slug, safe='')}"
    return RedirectResponse(url=location, status_code=status.HTTP_302_FOUND)


@router.post("/sso/{slug}/acs")
def sso_acs(
    slug: str,
    body: DevSsoAssertion,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    _auth_rate_limit(request)
    target = public_sso_target(db, slug)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SSO_NOT_FOUND)
    organization, connection = target
    pinned_id = pinned_organization_id(db, request)
    if pinned_id is not None and pinned_id != organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SSO_NOT_FOUND)
    settings = get_settings()
    if settings.sso_provider_name != "dev":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SSO_NOT_FOUND)
    if body.email_verified is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email is not verified",
        )
    principal = complete_sso_login(
        db,
        organization,
        connection,
        email=str(body.email),
        groups=list(body.groups or []),
    )
    enforce_host_pin(db, request, principal.organization_id, mode="login")
    db.commit()
    db.refresh(principal.user)
    if _sso_json_response(request):
        payload = user_response(db, principal)
        json_response = JSONResponse(content=payload.model_dump(mode="json"))
        _issue_session(principal, json_response, sso=True)
        return json_response
    redirect = RedirectResponse(url=f"{settings.public_frontend_url()}/", status_code=status.HTTP_302_FOUND)
    _issue_session(principal, redirect, sso=True)
    return redirect


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
    except HTTPException:
        revoke_refresh_token(raw)
        clear_auth_cookies(response)
        raise

    revoke_refresh_token(raw)
    _issue_session(principal, response, sso=sso_claim)
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
    _issue_session(principal, response, sso=organization.sso_enforced)
    return user_response(db, principal)
