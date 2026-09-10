import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.core.auth_cookies import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    create_refresh_token,
    decode_refresh_token,
    revoke_refresh_token,
    set_auth_cookies,
)
from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.core.principal import Principal
from app.core.security import create_access_token, hash_password, verify_password
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User, UserRole
from app.schemas.auth import GoogleAuthRequest, LoginRequest, RegisterRequest, SwitchOrganizationRequest
from app.schemas.user import UserResponse
from app.services.tenancy import (
    accept_invite,
    add_membership,
    create_organization,
    get_membership,
    get_pending_invite,
    principal_from_parts,
    resolve_principal,
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


def _issue_session(principal: Principal, response: Response) -> Principal:
    org_id = str(principal.organization_id)
    access = create_access_token(principal.email, role=principal.role, org_id=org_id)
    refresh = create_refresh_token(principal.email, role=principal.role, org_id=org_id)
    set_auth_cookies(response, access_token=access, refresh_token=refresh)
    return principal


def _principal_or_403(db: Session, user: User, organization_id: UUID | None) -> Principal:
    principal = resolve_principal(db, user, organization_id)
    if principal is None:
        membership = None
        if organization_id is not None:
            from app.services.tenancy import get_membership as _get

            membership = _get(db, user.id, organization_id)
        if membership is not None:
            org = db.get(Organization, membership.organization_id)
            if org is not None and org.status == OrganizationStatus.suspended.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Organization is suspended",
                )
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
    else:
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

    principal = _principal_or_403(db, user, None)
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
    if invite_token:
        invite = get_pending_invite(db, invite_token)
        membership = accept_invite(db, invite, user)
        target_org_id = membership.organization_id
    elif created:
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
    principal = _principal_or_403(db, user, target_org_id)
    _issue_session(principal, response)
    return user_response(db, principal)


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
    if principal is None:
        revoke_refresh_token(raw)
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    revoke_refresh_token(raw)
    _issue_session(principal, response)
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
    principal = principal_from_parts(current_user.user, membership, organization)
    _issue_session(principal, response)
    return user_response(db, principal)
