"""SSO HTTP: public ACS/login under `/auth/sso` and connector CRUD under `/organizations/sso`."""

from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.v1.auth.issue import issue_session
from app.core.config import get_settings
from app.core.csrf import CSRF_HEADER_VALUE
from app.core.deps import get_db, require_admin
from app.core.principal import Principal
from app.core.rate_limit import enforce_auth_rate_limit
from app.models.sso import OrganizationSsoConnection
from app.schemas.common import foreign_organization_id
from app.schemas.sso import DevSsoAssertion, SsoConnectionResponse, SsoUpsertRequest
from app.services.billing import NOT_FOUND
from app.services.domains import enforce_host_pin, pinned_organization_id
from app.services.sso import (
    SSO_NOT_FOUND,
    complete_sso_login,
    parse_attribute_map,
    public_sso_target,
    require_sso_entitlement,
    sso_paths,
)
from app.services.tenancy import user_response

public_router = APIRouter(prefix="/auth", tags=["sso"])
admin_router = APIRouter(prefix="/organizations", tags=["sso"])


def _sso_json_response(request: Request) -> bool:
    header = (request.headers.get("x-requested-with") or "").strip()
    if header == CSRF_HEADER_VALUE:
        return True
    accept = (request.headers.get("accept") or "").lower()
    return "application/json" in accept and "text/html" not in accept


def _sso_response(org, connection: OrganizationSsoConnection | None) -> SsoConnectionResponse:
    login_path, acs_path = sso_paths(org.slug)
    settings = get_settings()
    if connection is None:
        return SsoConnectionResponse(
            configured=False,
            slug=org.slug,
            protocol="saml",
            idp_entity_id=None,
            idp_metadata={},
            jit_enabled=False,
            attribute_map=parse_attribute_map({}),
            sso_enforced=bool(org.sso_enforced),
            login_path=login_path,
            acs_path=acs_path,
            provider=settings.sso_provider_name,
        )
    return SsoConnectionResponse(
        configured=True,
        slug=org.slug,
        protocol=connection.protocol,
        idp_entity_id=connection.idp_entity_id,
        idp_metadata=dict(connection.idp_metadata or {}),
        jit_enabled=bool(connection.jit_enabled),
        attribute_map=parse_attribute_map(connection.attribute_map),
        sso_enforced=bool(org.sso_enforced),
        login_path=login_path,
        acs_path=acs_path,
        provider=settings.sso_provider_name,
    )


@public_router.get("/sso/{slug}/login")
def sso_login(slug: str, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    enforce_auth_rate_limit(request)
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


@public_router.post("/sso/{slug}/acs")
def sso_acs(
    slug: str,
    body: DevSsoAssertion,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    enforce_auth_rate_limit(request)
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
        issue_session(principal, json_response, sso=True)
        return json_response
    redirect = RedirectResponse(url=f"{settings.public_frontend_url()}/", status_code=status.HTTP_302_FOUND)
    issue_session(principal, redirect, sso=True)
    return redirect


@admin_router.get("/sso", response_model=SsoConnectionResponse)
def get_organization_sso(
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> SsoConnectionResponse:
    org = current_user.organization
    require_sso_entitlement(org)
    connection = (
        db.query(OrganizationSsoConnection)
        .filter(OrganizationSsoConnection.organization_id == org.id)
        .first()
    )
    return _sso_response(org, connection)


@admin_router.put("/sso", response_model=SsoConnectionResponse)
def upsert_organization_sso(
    body: SsoUpsertRequest,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> SsoConnectionResponse:
    if foreign_organization_id(body, current_user.organization_id) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    org = current_user.organization
    require_sso_entitlement(org)
    attribute_map = parse_attribute_map(body.attribute_map)
    metadata = body.idp_metadata if isinstance(body.idp_metadata, dict) else {}
    entity_id = (body.idp_entity_id or "").strip() or None
    connection = (
        db.query(OrganizationSsoConnection)
        .filter(OrganizationSsoConnection.organization_id == org.id)
        .first()
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    if connection is None:
        connection = OrganizationSsoConnection(
            organization_id=org.id,
            protocol=body.protocol.value,
            idp_entity_id=entity_id,
            idp_metadata=metadata,
            attribute_map=attribute_map,
            jit_enabled=body.jit_enabled,
            updated_at=now,
        )
        db.add(connection)
    else:
        connection.protocol = body.protocol.value
        connection.idp_entity_id = entity_id
        connection.idp_metadata = metadata
        connection.attribute_map = attribute_map
        connection.jit_enabled = body.jit_enabled
        connection.updated_at = now
    org.sso_enforced = body.sso_enforced
    db.add(org)
    db.commit()
    db.refresh(org)
    db.refresh(connection)
    return _sso_response(org, connection)
