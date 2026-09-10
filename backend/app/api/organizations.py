import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_db, require_admin
from app.core.principal import Principal
from app.models.organization import OrganizationSsoConnection
from app.models.user import User
from app.schemas.billing import foreign_organization_id
from app.schemas.domain import DomainUpsertRequest, DomainVerifyRequest, OrganizationDomainResponse
from app.schemas.organization import (
    InviteCreateRequest,
    InviteCreateResponse,
    MemberListResponse,
    MemberResponse,
)
from app.schemas.sso import SsoConnectionResponse, SsoUpsertRequest
from app.services.billing import NOT_FOUND
from app.services.domains import (
    attach_platform_domains,
    custom_domain_for_org,
    domain_response,
    upsert_custom_domain,
    verify_custom_domain,
)
from app.services.sso import parse_attribute_map, require_sso_entitlement, sso_paths
from app.services.tenancy import add_membership, create_invite, list_members

router = APIRouter(prefix="/organizations", tags=["organizations"])

ROLE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")
MAX_DEPARTMENTS = 16


def _departments(raw: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        role = item.strip().lower()
        if not role:
            continue
        if not ROLE_RE.match(role):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid departments value")
        if role not in seen:
            seen.add(role)
            normalized.append(role)
    if len(normalized) > MAX_DEPARTMENTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many departments")
    return normalized


@router.get("/members", response_model=MemberListResponse)
def list_organization_members(
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> MemberListResponse:
    rows = list_members(db, current_user.organization_id)
    items = [
        MemberResponse(
            user_id=user.id,
            email=user.email,
            role=membership.role,
            departments=list(membership.departments or []),
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]
    return MemberListResponse(items=items, total=len(items))


@router.post("/invites", response_model=InviteCreateResponse, status_code=status.HTTP_201_CREATED)
def create_organization_invite(
    body: InviteCreateRequest,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> InviteCreateResponse:
    email = str(body.email).strip().lower()
    departments = _departments(body.departments)
    role = body.role.value
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        from app.services.tenancy import get_membership

        if get_membership(db, existing.id, current_user.organization_id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this organization",
            )
        add_membership(
            db,
            organization=current_user.organization,
            user=existing,
            role=role,
            departments=departments,
        )
        db.commit()
        return InviteCreateResponse(
            email=email,
            role=role,
            departments=departments,
            status="added",
            invite_token=None,
        )

    _invite, token = create_invite(
        db,
        organization=current_user.organization,
        email=email,
        role=role,
        departments=departments,
        invited_by=current_user.user,
    )
    db.commit()
    return InviteCreateResponse(
        email=email,
        role=role,
        departments=departments,
        status="invited",
        invite_token=token,
    )


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


@router.get("/sso", response_model=SsoConnectionResponse)
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


@router.put("/sso", response_model=SsoConnectionResponse)
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


@router.get("/domain", response_model=OrganizationDomainResponse)
def get_organization_domain(
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> OrganizationDomainResponse:
    org = current_user.organization
    attach_platform_domains(db, org)
    db.commit()
    db.refresh(org)
    custom = custom_domain_for_org(db, org.id)
    return OrganizationDomainResponse.model_validate(domain_response(org, custom))


@router.put("/domain", response_model=OrganizationDomainResponse)
def upsert_organization_domain(
    body: DomainUpsertRequest,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> OrganizationDomainResponse:
    if foreign_organization_id(body, current_user.organization_id) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    org = current_user.organization
    attach_platform_domains(db, org)
    custom = upsert_custom_domain(db, org, body.hostname)
    db.commit()
    db.refresh(org)
    if custom is not None:
        db.refresh(custom)
    return OrganizationDomainResponse.model_validate(domain_response(org, custom))


@router.post("/domain/verify", response_model=OrganizationDomainResponse)
def verify_organization_domain(
    body: DomainVerifyRequest,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> OrganizationDomainResponse:
    if foreign_organization_id(body, current_user.organization_id) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    org = current_user.organization
    custom = verify_custom_domain(db, org, body.token)
    db.commit()
    db.refresh(custom)
    return OrganizationDomainResponse.model_validate(domain_response(org, custom))
