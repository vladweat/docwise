"""Org members and invites (`require_admin` of current org)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.principal import Principal
from app.models.user import User
from app.schemas.organization import (
    InviteCreateRequest,
    InviteCreateResponse,
    MemberListResponse,
    MemberResponse,
)
from app.services.org.tenancy import add_membership, create_invite, list_members
from app.services.text import InvalidRoleTag, TooManyRoleTags, normalize_role_tags

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _departments(raw: list[str]) -> list[str]:
    try:
        return normalize_role_tags(raw)
    except InvalidRoleTag as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid departments value") from exc
    except TooManyRoleTags as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many departments") from exc


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
        from app.services.org.tenancy import get_membership

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
