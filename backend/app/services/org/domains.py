"""Custom and platform hostnames. Host pins org; it never replaces SQL organization_id."""

from __future__ import annotations

import re
import secrets
from urllib.parse import urlparse
from uuid import UUID

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.time import utcnow_naive
from app.models.domain import DomainKind, OrganizationDomain
from app.models.organization import Organization, OrganizationStatus
from app.services.org.quotas import plan_limits

DOMAIN_NOT_IN_PLAN = "Custom domain is not included in the current plan"
HOSTNAME_IN_USE = "Hostname already in use"
HOSTNAME_INVALID = "Invalid hostname"
HOSTNAME_RESERVED = "Hostname is reserved for a platform host"
HOST_SWITCH_DENIED = "Cannot switch organization on this host"
HOST_REGISTER_DENIED = "Cannot create an organization on this host"
DOMAIN_NOT_FOUND = "Not found"
VERIFY_FAILED = "Domain verification failed"

_GENERIC_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "testserver",
        "backend",
        "frontend",
        "host.docker.internal",
    }
)
_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$"
)


def platform_suffixes() -> tuple[str, ...]:
    settings = get_settings()
    raw = (settings.platform_host_suffixes or "localhost,docwise.app").strip()
    items = [item.strip().lower().lstrip(".") for item in raw.split(",") if item.strip()]
    return tuple(items) or ("localhost", "docwise.app")


def platform_hostnames_for_slug(slug: str) -> list[str]:
    cleaned = (slug or "").strip().lower()
    if not cleaned:
        return []
    return [f"{cleaned}.{suffix}" for suffix in platform_suffixes()]


def normalize_hostname(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return ""
    if "://" in value:
        parsed = urlparse(value if "://" in value else f"//{value}")
        value = (parsed.hostname or "").strip().lower()
        return value
    if value.startswith("[") and "]" in value:
        return value[1 : value.find("]")].lower()
    if value.count(":") == 1:
        host, port = value.rsplit(":", 1)
        if port.isdigit():
            return host.strip().lower()
    return value


def request_hostname(request: Request) -> str:
    return normalize_hostname(request.headers.get("host") or "")


def _valid_hostname(hostname: str) -> bool:
    if not hostname or not _HOSTNAME_RE.match(hostname):
        return False
    labels = hostname.split(".")
    return all(_LABEL_RE.match(label) for label in labels)


def slug_from_platform_hostname(hostname: str) -> str | None:
    for suffix in platform_suffixes():
        ending = f".{suffix}"
        if hostname.endswith(ending):
            rest = hostname[: -len(ending)]
            if rest and "." not in rest and _LABEL_RE.match(rest):
                return rest
    return None


def origin_hostname(origin: str) -> str:
    parsed = urlparse((origin or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return ""
    return (parsed.hostname or "").strip().lower()


def is_localhost_hostname(hostname: str) -> bool:
    """RFC 6761 loopback. Compose tenant hosts are `{slug}.localhost` or `{cname}.localhost`."""
    return hostname == "localhost" or hostname.endswith(".localhost")


def compose_alias_hostname(hostname: str) -> str | None:
    """`kb.acme.example.localhost` → `kb.acme.example` (multi-label only; `{slug}.localhost` stays a platform host)."""
    if not hostname.endswith(".localhost"):
        return None
    prefix = hostname[: -len(".localhost")]
    if "." in prefix:
        return prefix
    return None


def _utcnow():
    return utcnow_naive()


def attach_platform_domains(db: Session, organization: Organization) -> None:
    now = _utcnow()
    existing = {
        row.hostname
        for row in db.query(OrganizationDomain)
        .filter(OrganizationDomain.organization_id == organization.id)
        .all()
    }
    for hostname in platform_hostnames_for_slug(organization.slug):
        if hostname in existing:
            continue
        db.add(
            OrganizationDomain(
                organization_id=organization.id,
                hostname=hostname,
                kind=DomainKind.platform.value,
                verified_at=now,
            )
        )
    db.flush()


def require_custom_domain_entitlement(organization: Organization) -> None:
    if not plan_limits(organization.plan).custom_domain:
        raise ForbiddenError(DOMAIN_NOT_IN_PLAN)


def _active_org(db: Session, organization_id: UUID) -> Organization | None:
    organization = db.get(Organization, organization_id)
    if organization is None or organization.status != OrganizationStatus.active.value:
        return None
    return organization


def resolve_bound_organization(db: Session, host: str | None) -> Organization | None:
    """Map Host to an org only when the hostname is platform or verified custom.

    Does not become the SQL tenant filter — callers still use session org_id.
    """
    hostname = normalize_hostname(host)
    if not hostname or hostname in _GENERIC_HOSTS:
        return None
    row = (
        db.query(OrganizationDomain)
        .filter(OrganizationDomain.hostname == hostname)
        .first()
    )
    if row is not None:
        bound = row.kind == DomainKind.platform.value or row.verified_at is not None
        if not bound:
            return None
        return _active_org(db, row.organization_id)
    alias = compose_alias_hostname(hostname)
    if alias is not None:
        return resolve_bound_organization(db, alias)
    slug = slug_from_platform_hostname(hostname)
    if slug is None:
        return None
    organization = db.query(Organization).filter(Organization.slug == slug).first()
    if organization is None or organization.status != OrganizationStatus.active.value:
        return None
    return organization


def hostname_is_bound(db: Session, hostname: str) -> bool:
    return resolve_bound_organization(db, hostname) is not None


def origin_allowed(origin: str) -> bool:
    """CORS/CSRF allowlist: configured frontends, loopback, verified/platform hosts."""
    cleaned = (origin or "").rstrip("/")
    settings = get_settings()
    static = {item.rstrip("/") for item in settings.cors_origin_list()}
    if cleaned in static:
        return True
    host = origin_hostname(origin)
    if not host:
        return False
    if is_localhost_hostname(host) or host in {"127.0.0.1", "::1"}:
        return True
    db = SessionLocal()
    try:
        return hostname_is_bound(db, host)
    finally:
        db.close()


def enforce_host_pin(
    db: Session,
    request: Request,
    organization_id: UUID,
    *,
    mode: str = "session",
) -> None:
    pinned = resolve_bound_organization(db, request_hostname(request))
    if pinned is None or pinned.id == organization_id:
        return
    if mode == "switch":
        raise ForbiddenError(HOST_SWITCH_DENIED)
    if mode == "register":
        raise ForbiddenError(HOST_REGISTER_DENIED)
    if mode == "login":
        raise ForbiddenError("No organization membership")
    raise UnauthorizedError("Not authenticated")


def pinned_organization_id(db: Session, request: Request) -> UUID | None:
    pinned = resolve_bound_organization(db, request_hostname(request))
    return None if pinned is None else pinned.id


def custom_domain_for_org(db: Session, organization_id: UUID) -> OrganizationDomain | None:
    return (
        db.query(OrganizationDomain)
        .filter(
            OrganizationDomain.organization_id == organization_id,
            OrganizationDomain.kind == DomainKind.custom.value,
        )
        .first()
    )


def domain_response(organization: Organization, custom: OrganizationDomain | None) -> dict:
    token = None
    if custom is not None and custom.verified_at is None:
        token = custom.verification_token
    return {
        "slug": organization.slug,
        "platform_hostnames": platform_hostnames_for_slug(organization.slug),
        "custom_hostname": None if custom is None else custom.hostname,
        "custom_verified": bool(custom is not None and custom.verified_at is not None),
        "verified_at": None if custom is None else custom.verified_at,
        "verification_token": token,
        "entitlement": plan_limits(organization.plan).custom_domain,
    }


def _normalize_custom_hostname(raw: str) -> str:
    hostname = normalize_hostname(raw)
    if not hostname or not _valid_hostname(hostname) or hostname in _GENERIC_HOSTS:
        raise BadRequestError(HOSTNAME_INVALID)
    return hostname


def upsert_custom_domain(db: Session, organization: Organization, hostname: str | None) -> OrganizationDomain | None:
    existing = custom_domain_for_org(db, organization.id)
    cleaned = (hostname or "").strip()
    if not cleaned:
        if existing is not None:
            db.delete(existing)
            db.flush()
        return None
    require_custom_domain_entitlement(organization)
    normalized = _normalize_custom_hostname(cleaned)
    if normalized in platform_suffixes():
        raise BadRequestError(HOSTNAME_RESERVED)
    if normalized in set(platform_hostnames_for_slug(organization.slug)):
        return existing
    platform_slug = slug_from_platform_hostname(normalized)
    if platform_slug is not None:
        other = db.query(Organization).filter(Organization.slug == platform_slug).first()
        if other is not None and other.id != organization.id:
            raise ConflictError(HOSTNAME_IN_USE)
        if other is not None:
            return existing
    taken = (
        db.query(OrganizationDomain)
        .filter(
            OrganizationDomain.hostname == normalized,
            OrganizationDomain.organization_id != organization.id,
        )
        .first()
    )
    if taken is not None:
        raise ConflictError(HOSTNAME_IN_USE)
    token = secrets.token_urlsafe(24)
    try:
        with db.begin_nested():
            if existing is None:
                existing = OrganizationDomain(
                    organization_id=organization.id,
                    hostname=normalized,
                    kind=DomainKind.custom.value,
                    verified_at=None,
                    verification_token=token,
                )
                db.add(existing)
            elif existing.hostname != normalized:
                existing.hostname = normalized
                existing.verified_at = None
                existing.verification_token = token
            db.flush()
    except IntegrityError as exc:
        raise ConflictError(HOSTNAME_IN_USE) from exc
    return existing


def verify_custom_domain(
    db: Session,
    organization: Organization,
    token: str | None,
) -> OrganizationDomain:
    require_custom_domain_entitlement(organization)
    custom = custom_domain_for_org(db, organization.id)
    if custom is None:
        raise NotFoundError(DOMAIN_NOT_FOUND)
    if custom.verified_at is not None:
        return custom
    expected = (custom.verification_token or "").strip()
    provided = (token or "").strip()
    if not expected or provided != expected:
        raise BadRequestError(VERIFY_FAILED)
    custom.verified_at = _utcnow()
    db.flush()
    return custom
