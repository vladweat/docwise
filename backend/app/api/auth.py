import logging

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
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import GoogleAuthRequest, LoginRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.utils.rate_limit import client_ip, enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def verify_google_id_token(token: str, client_id: str) -> dict:
    return id_token.verify_oauth2_token(token, google_requests.Request(), client_id)


def _auth_rate_limit(request: Request) -> None:
    settings = get_settings()
    enforce_rate_limit("auth", client_ip(request), settings.rate_limit_auth_per_minute)


def _bootstrap_role(db: Session) -> str:
    if db.query(User.id).first() is None:
        return UserRole.admin.value
    return UserRole.employee.value


def _issue_session(user: User, response: Response) -> User:
    access = create_access_token(user.email, role=user.role)
    refresh = create_refresh_token(user.email, role=user.role)
    set_auth_cookies(response, access_token=access, refresh_token=refresh)
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    _auth_rate_limit(request)
    existing = db.query(User).filter(User.email == body.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=_bootstrap_role(db),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_session(user, response)


@router.post("/login", response_model=UserResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    _auth_rate_limit(request)
    user = db.query(User).filter(User.email == body.email).first()
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

    return _issue_session(user, response)


@router.post("/google", response_model=UserResponse)
def google_auth(
    body: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
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

    user = db.query(User).filter(User.google_id == google_sub).first()
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
            user = User(email=email, google_id=google_sub, role=_bootstrap_role(db))
            db.add(user)

    if user.is_active is False:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")

    db.commit()
    db.refresh(user)
    return _issue_session(user, response)


@router.post("/refresh", response_model=UserResponse)
def refresh_session(request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_refresh_token(raw)
        email = payload.get("sub")
    except ValueError:
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

    revoke_refresh_token(raw)
    return _issue_session(user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        revoke_refresh_token(raw)
    clear_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
