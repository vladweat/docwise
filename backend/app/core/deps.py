from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth_cookies import ACCESS_COOKIE
from app.core.database import SessionLocal
from app.core.principal import Principal
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.services.org.domains import enforce_host_pin
from app.services.org.sso import session_allowed_for_org
from app.services.org.tenancy import resolve_principal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _org_id_from_payload(payload: dict) -> UUID | None:
    raw = payload.get("org_id") or payload.get("organization_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Principal:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_access_token(token)
        if payload.get("typ") == "refresh":
            raise ValueError("Invalid token")
        email: str | None = payload.get("sub")
        org_id = _org_id_from_payload(payload)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    principal = resolve_principal(db, user, org_id)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    if not session_allowed_for_org(principal.organization, sso_claim=payload.get("sso") is True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    enforce_host_pin(db, request, principal.organization_id, mode="session")
    return principal


def require_admin(current_user: Principal = Depends(get_current_user)) -> Principal:
    if current_user.role != UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_kb_admin(current_user: Principal = Depends(get_current_user)) -> Principal:
    """KB write: org admin or manager. Billing, SSO, domain, inspect stay require_admin."""
    if current_user.role not in {UserRole.admin.value, UserRole.manager.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
