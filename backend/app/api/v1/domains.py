"""Custom domain HTTP under `/organizations/domain`. Host pins org; it is not the tenant id."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.principal import Principal
from app.schemas.common import foreign_organization_id
from app.schemas.domain import DomainUpsertRequest, DomainVerifyRequest, OrganizationDomainResponse
from app.services.billing import NOT_FOUND
from app.services.domains import (
    attach_platform_domains,
    custom_domain_for_org,
    domain_response,
    upsert_custom_domain,
    verify_custom_domain,
)

router = APIRouter(prefix="/organizations", tags=["domains"])


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
