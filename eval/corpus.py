"""Synthetic eval PDFs with stable UUIDs and mixed ACL tags."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from uuid import UUID

import fitz

logger = logging.getLogger(__name__)

A4 = (595.0, 842.0)

HANDBOOK_ID = UUID("aaaaaaaa-1111-4111-8111-000000000001")
LEAVE_ID = UUID("aaaaaaaa-1111-4111-8111-000000000002")
EXPENSE_ID = UUID("aaaaaaaa-1111-4111-8111-000000000003")
ENGINEERING_ID = UUID("aaaaaaaa-1111-4111-8111-000000000004")
HR_COMP_ID = UUID("aaaaaaaa-1111-4111-8111-000000000005")
FINANCE_ID = UUID("aaaaaaaa-1111-4111-8111-000000000006")
FOREIGN_ORG_DOC_ID = UUID("bbbbbbbb-2222-4222-8222-000000000099")

DEFAULT_EVAL_EMAIL = "eval-employee@docwise.example.com"
DEFAULT_EVAL_PASSWORD = "eval-employee-pass"

RESTRICTED_DOC_IDS = (str(HR_COMP_ID), str(FINANCE_ID))
EVAL_ORG_SLUG = "eval"
DEMO_ORG_SLUG = "demo"
FOREIGN_ORG_SLUG = "eval-foreign"

DEMO_ADMIN_EMAIL = "admin@docwise.example.com"
DEMO_EMPLOYEE_EMAIL = "employee@docwise.example.com"
DEMO_HR_EMAIL = "hr@docwise.example.com"
DEMO_ADMIN_PASSWORD = "demo-admin-pass"
DEMO_EMPLOYEE_PASSWORD = "demo-employee-pass"
DEMO_HR_PASSWORD = "demo-hr-pass"
DEMO_HANDBOOK_ID = UUID("cccccccc-3333-4333-8333-000000000001")
DEMO_LEAVE_ID = UUID("cccccccc-3333-4333-8333-000000000002")
DEMO_EXPENSE_ID = UUID("cccccccc-3333-4333-8333-000000000003")
DEMO_ENGINEERING_ID = UUID("cccccccc-3333-4333-8333-000000000004")
DEMO_HR_COMP_ID = UUID("cccccccc-3333-4333-8333-000000000005")
DEMO_FINANCE_ID = UUID("cccccccc-3333-4333-8333-000000000006")
DEMO_SECURITY_ID = UUID("cccccccc-3333-4333-8333-000000000007")
DEMO_RECRUITING_ID = UUID("cccccccc-3333-4333-8333-000000000008")
DEMO_TRAVEL_ID = UUID("cccccccc-3333-4333-8333-000000000009")
DEMO_IT_CHECKLIST_ID = UUID("cccccccc-3333-4333-8333-00000000000a")
DEMO_OPERATIONS_ID = UUID("cccccccc-3333-4333-8333-00000000000b")
DEMO_PEOPLE_ID = UUID("cccccccc-3333-4333-8333-00000000000c")

DEMO_DOC_SLUGS = (
    "employee-handbook",
    "leave-policy",
    "expense-policy",
    "engineering-onboarding",
    "hr-compensation",
    "finance-q4",
    "security-runbook",
    "recruiting-faq",
    "travel-policy",
    "it-access-checklist",
    "operations-handbook",
    "people-compendium",
)


@dataclass(frozen=True)
class FixtureSpec:
    id: UUID
    slug: str
    filename: str
    access_roles: tuple[str, ...]
    builder: str


@dataclass(frozen=True)
class DemoAccount:
    email: str
    password: str
    role: str
    departments: tuple[str, ...]


CATALOG: tuple[FixtureSpec, ...] = (
    FixtureSpec(HANDBOOK_ID, "employee-handbook", "Employee-Handbook.pdf", ("all",), "handbook"),
    FixtureSpec(LEAVE_ID, "leave-policy", "Leave-Policy.pdf", ("all",), "leave"),
    FixtureSpec(EXPENSE_ID, "expense-policy", "Expense-Policy.pdf", ("all",), "expense"),
    FixtureSpec(ENGINEERING_ID, "engineering-onboarding", "Engineering-Onboarding.pdf", ("all",), "engineering"),
    FixtureSpec(HR_COMP_ID, "hr-compensation", "HR-Compensation.pdf", ("hr",), "hr_comp"),
    FixtureSpec(FINANCE_ID, "finance-q4", "Finance-Q4-Memo.pdf", ("finance",), "finance"),
)

CATALOG_BY_ID = {str(item.id): item for item in CATALOG}

DEMO_ACCOUNTS: tuple[DemoAccount, ...] = (
    DemoAccount(DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, "admin", ()),
    DemoAccount(DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD, "employee", ()),
    DemoAccount(DEMO_HR_EMAIL, DEMO_HR_PASSWORD, "employee", ("hr",)),
)


DEMO_CATALOG: tuple[FixtureSpec, ...] = (
    FixtureSpec(DEMO_HANDBOOK_ID, "employee-handbook", "Employee-Handbook.pdf", ("all",), "handbook"),
    FixtureSpec(DEMO_LEAVE_ID, "leave-policy", "Leave-Policy.pdf", ("all",), "leave"),
    FixtureSpec(DEMO_EXPENSE_ID, "expense-policy", "Expense-Policy.pdf", ("all",), "expense"),
    FixtureSpec(DEMO_ENGINEERING_ID, "engineering-onboarding", "Engineering-Onboarding.pdf", ("all",), "engineering"),
    FixtureSpec(DEMO_HR_COMP_ID, "hr-compensation", "HR-Compensation.pdf", ("hr",), "hr_comp"),
    FixtureSpec(DEMO_FINANCE_ID, "finance-q4", "Finance-Q4-Memo.pdf", ("finance",), "finance"),
    FixtureSpec(DEMO_SECURITY_ID, "security-runbook", "Security-Runbook.pdf", ("all",), "security"),
    FixtureSpec(DEMO_RECRUITING_ID, "recruiting-faq", "Recruiting-FAQ.pdf", ("hr",), "recruiting"),
    FixtureSpec(DEMO_TRAVEL_ID, "travel-policy", "Travel-Policy.pdf", ("all",), "travel"),
    FixtureSpec(DEMO_IT_CHECKLIST_ID, "it-access-checklist", "IT-Access-Checklist.pdf", ("all",), "it_checklist"),
    FixtureSpec(DEMO_OPERATIONS_ID, "operations-handbook", "Operations-Handbook.pdf", ("all",), "operations"),
    FixtureSpec(DEMO_PEOPLE_ID, "people-compendium", "People-Compendium.pdf", ("hr",), "people"),
)


def restricted_doc_ids() -> tuple[str, ...]:
    return RESTRICTED_DOC_IDS


def demo_specs() -> tuple[FixtureSpec, ...]:
    return DEMO_CATALOG


def demo_fixture_document_ids() -> frozenset[UUID]:
    return frozenset(spec.id for spec in DEMO_CATALOG)


def build_pdf(spec: FixtureSpec) -> bytes:
    builders = {
        "handbook": _handbook_pdf,
        "leave": _leave_pdf,
        "expense": _expense_pdf,
        "engineering": _engineering_pdf,
        "hr_comp": _hr_comp_pdf,
        "finance": _finance_pdf,
        "security": _security_pdf,
        "recruiting": _recruiting_pdf,
        "travel": _travel_pdf,
        "it_checklist": _it_access_checklist_pdf,
        "operations": _operations_handbook_pdf,
        "people": _people_compendium_pdf,
    }
    return builders[spec.builder]()


def get_or_create_org(db, *, name: str, slug: str):
    from app.models.organization import Organization, OrganizationPlan, OrganizationStatus

    org = db.query(Organization).filter(Organization.slug == slug).first()
    if org is None:
        org = Organization(
            name=name,
            slug=slug,
            status=OrganizationStatus.active.value,
            plan=OrganizationPlan.enterprise.value,
        )
        db.add(org)
        db.flush()
        from app.services.org.domains import attach_platform_domains

        attach_platform_domains(db, org)
        logger.info("created organization %s slug=%s", name, slug)
    else:
        org.name = name
        org.status = OrganizationStatus.active.value
        org.plan = OrganizationPlan.enterprise.value
    return org


def upsert_user(
    db,
    *,
    email: str,
    password: str,
    role: str,
    departments: list[str] | tuple[str, ...],
    organization,
    reset_password: bool = False,
):
    """Create or update a local user and membership in `organization`."""
    from app.core.security import hash_password
    from app.models.organization import OrganizationMembership
    from app.models.user import User

    dept_list = list(departments)
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.flush()
        logger.info("created user %s", email)
    else:
        user.is_active = True
        if reset_password or not user.hashed_password:
            user.hashed_password = hash_password(password)
        logger.info("updated user %s", email)

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization.id,
        )
        .first()
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=role,
            departments=dept_list,
        )
        db.add(membership)
        db.flush()
    else:
        membership.role = role
        membership.departments = dept_list
    logger.info(
        "membership %s org=%s role=%s departments=%s",
        email,
        organization.slug,
        role,
        dept_list,
    )
    return user, membership


def index_specs(db, storage, specs: tuple[FixtureSpec, ...] | list[FixtureSpec], *, organization) -> list[dict]:
    from app.models.document import Document, DocumentStatus
    from app.services.ingestion import delete_chunks_for_document, index_pdf
    from app.services.storage import object_key_for_document

    indexed: list[dict] = []
    for spec in specs:
        pdf_bytes = build_pdf(spec)
        digest = hashlib.sha256(pdf_bytes).hexdigest()
        conflict = (
            db.query(Document)
            .filter(
                Document.organization_id == organization.id,
                Document.file_hash == digest,
                Document.id != spec.id,
            )
            .first()
        )
        if conflict is not None:
            raise RuntimeError(
                f"Fixture hash collides with existing document {conflict.id} ({conflict.title}). "
                "Delete that row or skip seeding."
            )
        key = object_key_for_document(spec.id, spec.filename, organization_id=organization.id)
        storage.put_bytes(key, pdf_bytes, content_type="application/pdf")
        document = db.get(Document, spec.id)
        if document is not None:
            delete_chunks_for_document(db, document.id)
            db.flush()
        if document is None:
            document = Document(
                id=spec.id,
                organization_id=organization.id,
                title=spec.filename,
                file_path=key,
                file_hash=digest,
                file_size_bytes=len(pdf_bytes),
                access_roles=list(spec.access_roles),
                status=DocumentStatus.processing.value,
            )
            db.add(document)
        else:
            document.organization_id = organization.id
            document.title = spec.filename
            document.file_path = key
            document.file_hash = digest
            document.file_size_bytes = len(pdf_bytes)
            document.access_roles = list(spec.access_roles)
            document.status = DocumentStatus.processing.value
            document.last_error = None
        db.commit()
        db.refresh(document)
        delete_chunks_for_document(db, document.id)
        result = index_pdf(db, document, pdf_bytes)
        document.total_pages = result.total_pages
        document.status = DocumentStatus.ready.value
        document.last_error = None
        document.ingestion_stage = "embed"
        db.commit()
        indexed.append(
            {
                "id": str(spec.id),
                "slug": spec.slug,
                "access_roles": list(spec.access_roles),
                "chunks": result.chunk_count,
                "pages": result.total_pages,
            }
        )
        logger.info(
            "seeded %s id=%s roles=%s chunks=%s",
            spec.filename,
            spec.id,
            spec.access_roles,
            result.chunk_count,
        )
    return indexed


def seed_corpus(*, email: str | None = None, password: str | None = None) -> dict:
    """Upsert fixture PDFs and the employee eval user, then run real `index_pdf`."""
    from app.core.database import SessionLocal
    from app.core.rls import bind_session_rls
    from app.models.user import UserRole
    from app.services.storage import get_object_storage

    eval_email = (email or os.environ.get("EVAL_USER_EMAIL") or DEFAULT_EVAL_EMAIL).strip()
    eval_password = password or os.environ.get("EVAL_USER_PASSWORD") or DEFAULT_EVAL_PASSWORD

    db = SessionLocal()
    bind_session_rls(db, bypass=True)
    storage = get_object_storage()
    storage.ensure_private_bucket()
    try:
        organization = get_or_create_org(db, name="Eval", slug=EVAL_ORG_SLUG)
        upsert_user(
            db,
            email=eval_email,
            password=eval_password,
            role=UserRole.employee.value,
            departments=[],
            organization=organization,
            reset_password=False,
        )
        db.commit()
        indexed = index_specs(db, storage, CATALOG, organization=organization)
        foreign = _seed_foreign_org(db, storage)
        return {
            "eval_user_email": eval_email,
            "organization_id": str(organization.id),
            "documents": indexed,
            "foreign_org_document_id": str(foreign),
        }
    finally:
        db.close()


def _seed_foreign_org(db, storage) -> UUID:
    from app.models.document import Document, DocumentStatus
    from app.services.ingestion import delete_chunks_for_document, index_pdf
    from app.services.storage import object_key_for_document

    organization = get_or_create_org(db, name="Eval Foreign", slug=FOREIGN_ORG_SLUG)
    spec = CATALOG[0]
    pdf_bytes = build_pdf(spec)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    key = object_key_for_document(FOREIGN_ORG_DOC_ID, "Foreign-Org-Handbook.pdf", organization_id=organization.id)
    storage.put_bytes(key, pdf_bytes, content_type="application/pdf")
    document = db.get(Document, FOREIGN_ORG_DOC_ID)
    if document is None:
        document = Document(
            id=FOREIGN_ORG_DOC_ID,
            organization_id=organization.id,
            title="Foreign-Org-Handbook.pdf",
            file_path=key,
            file_hash=digest,
            file_size_bytes=len(pdf_bytes),
            access_roles=["all"],
            status=DocumentStatus.processing.value,
        )
        db.add(document)
    else:
        document.organization_id = organization.id
        document.title = "Foreign-Org-Handbook.pdf"
        document.file_path = key
        document.file_hash = digest
        document.access_roles = ["all"]
        document.status = DocumentStatus.processing.value
        document.last_error = None
    db.commit()
    db.refresh(document)
    delete_chunks_for_document(db, document.id)
    result = index_pdf(db, document, pdf_bytes)
    document.total_pages = result.total_pages
    document.status = DocumentStatus.ready.value
    document.last_error = None
    document.ingestion_stage = "embed"
    db.commit()
    logger.info("seeded foreign-org document id=%s", document.id)
    return document.id


def seed_demo() -> dict:
    """Upsert demo users and the six-PDF catalog (all / hr / finance ACLs)."""
    from app.core.database import SessionLocal
    from app.core.rls import bind_session_rls
    from app.services.storage import get_object_storage

    db = SessionLocal()
    bind_session_rls(db, bypass=True)
    storage = get_object_storage()
    storage.ensure_private_bucket()
    try:
        organization = get_or_create_org(db, name="Demo", slug=DEMO_ORG_SLUG)
        users = []
        for account in DEMO_ACCOUNTS:
            user, membership = upsert_user(
                db,
                email=account.email,
                password=account.password,
                role=account.role,
                departments=account.departments,
                organization=organization,
                reset_password=True,
            )
            _keep_only_demo_membership(db, user.id, organization.id)
            users.append(
                {
                    "email": user.email,
                    "role": membership.role,
                    "departments": list(membership.departments or []),
                }
            )
        db.commit()
        indexed = index_specs(db, storage, demo_specs(), organization=organization)
        return {"organization_id": str(organization.id), "users": users, "documents": indexed}
    finally:
        db.close()


def reset_demo_data() -> dict[str, int]:
    """Clear synthetic Demo chats/audit and user uploads, preserving seeded fixture rows."""
    from app.core.database import SessionLocal
    from app.core.rls import bind_session_rls
    from app.models.audit import RagAuditLog
    from app.models.chat import ChatSession
    from app.models.document import Document
    from app.models.organization import Organization
    from app.models.storage_deletion import StorageDeletion
    from app.services.chat.llm_cache import invalidate_llm_cache

    fixture_ids = demo_fixture_document_ids()
    db = SessionLocal()
    bind_session_rls(db, bypass=True)
    try:
        organization = db.query(Organization).filter(Organization.slug == DEMO_ORG_SLUG).first()
        if organization is None:
            return {"sessions": 0, "audit_logs": 0, "uploaded_documents": 0}

        sessions = db.query(ChatSession).filter(ChatSession.organization_id == organization.id).all()
        audit_logs = (
            db.query(RagAuditLog)
            .filter(RagAuditLog.organization_id == organization.id)
            .delete(synchronize_session=False)
        )
        for session in sessions:
            db.delete(session)

        uploaded_documents = (
            db.query(Document)
            .filter(
                Document.organization_id == organization.id,
                Document.id.notin_(fixture_ids),
            )
            .all()
        )
        for document in uploaded_documents:
            db.add(StorageDeletion(object_key=document.file_path))
            db.delete(document)

        invalidate_llm_cache(db, organization.id)
        db.commit()
        logger.info(
            "reset synthetic Demo data sessions=%s audit_logs=%s uploaded_documents=%s",
            len(sessions),
            audit_logs,
            len(uploaded_documents),
        )
        return {
            "sessions": len(sessions),
            "audit_logs": int(audit_logs),
            "uploaded_documents": len(uploaded_documents),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _keep_only_demo_membership(db, user_id, organization_id) -> None:
    """Reserved demo emails must land in org Demo on password login (first membership)."""
    from app.models.organization import OrganizationMembership

    extras = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id != organization_id,
        )
        .all()
    )
    for row in extras:
        db.delete(row)
    db.flush()


def _handbook_pdf() -> bytes:
    doc = fitz.open()
    _add_page(
        doc,
        "Work schedule",
        "Core working hours at Docwise are 09:00 to 18:00 Europe/Moscow. "
        "The unpaid lunch break is 13:00 to 14:00. "
        "The hybrid policy requires office attendance on Tuesday, Wednesday, and Thursday; "
        "Monday and Friday are remote days. "
        "A desk must be booked in the Places portal before 17:00 on the previous day.",
    )
    _add_page_sections(
        doc,
        [
            (
                "Device policy",
                "Employees must not store client personal data on personal devices.",
            ),
            (
                "Security reporting",
                "Security incidents must be emailed to security@docwise.example within one hour.",
            ),
            (
                "Gifts and publishing",
                "External blog posts about the product require legal review before publishing. "
                "Gifts from vendors over 50 USD must be declined.",
            ),
        ],
    )
    _add_page(
        doc,
        "Equipment",
        "The standard laptop warranty is 36 months. "
        "A lost badge replacement fee is 15 USD after the first free replacement. "
        "Hardware requests go through Service Desk category IT / Hardware. "
        "Docking stations are issued only to employees with an assigned office desk.",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _leave_pdf() -> bytes:
    doc = fitz.open()
    page1 = _add_page(
        doc,
        "Leave entitlements",
        "Employees are entitled to twenty days of paid vacation per calendar year. "
        "Paid sick leave is ten days. "
        "Vacation requests must be submitted at least fourteen days in advance.",
    )
    _draw_table(
        page1,
        origin=(72, 220),
        col_widths=[140.0, 80.0, 180.0],
        row_h=22.0,
        cells=[
            ["Benefit", "Days", "Notes"],
            ["Vacation", "20", "Annual leave"],
            ["Sick", "10", "Paid"],
        ],
    )
    _add_page(
        doc,
        "Extended leave",
        "Parental leave is 140 calendar days. "
        "Unused vacation may be carried over with a maximum of five days into the next year. "
        "Bereavement leave is three paid days. "
        "Unpaid leave requires approval from both the manager and HR.",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _expense_pdf() -> bytes:
    return _multi_page(
        [
            (
                "Local expenses",
                "Taxi receipts under forty US dollars do not need a manager signature. "
                "Keep original receipts attached to the monthly expense report. "
                "Meals during local client meetings are capped at 25 USD per person. "
                "Expense reports are due on the fifth business day of the following month.",
            ),
            (
                "Travel",
                "International travel requires VP approval at least ten calendar days ahead. "
                "The per diem for international trips is 75 USD per day. "
                "Business class flights are allowed only if in-air time exceeds eight hours. "
                "The company card limit for individual contributors is 3000 USD.",
            ),
        ]
    )


def _engineering_pdf() -> bytes:
    doc = fitz.open()
    _add_page(
        doc,
        "First week",
        "On day one, enable GitHub SSO via Okta and collect a laptop from the IT cage on floor 4. "
        "Each new hire is assigned a buddy for 30 days. "
        "Required reading is the employee handbook and the leave policy. "
        "The first pull request must be opened within five working days.",
    )
    _add_page_sections(
        doc,
        [
            (
                "Delivery",
                "Staging deploys use make up on the staging cluster. "
                "Production deploys need two approvers from the on-call rotation.",
            ),
            (
                "Toolchain",
                "The default Python version for engineering services is 3.12.",
            ),
            (
                "On-call rotation",
                "The on-call starter rotation begins after 90 days.",
            ),
        ],
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _hr_comp_pdf() -> bytes:
    return _multi_page(
        [
            (
                "Salary bands (HR only)",
                "The individual contributor L3 salary band is 72000 to 88000 USD. "
                "The L4 salary band is 95000 to 120000 USD. "
                "Promotion packets are due the first Monday of March and September. "
                "Compensation reviews are closed to employees outside HR.",
            ),
            (
                "Bonus and equity (HR only)",
                "The annual performance bonus target is 12 percent of base salary. "
                "Bonus payday is 15 March. "
                "Retention RSUs for L4 and above vest over four years. "
                "The CEO cash bonus multiplier for this fiscal year is 1.8x.",
            ),
        ]
    )


def _finance_pdf() -> bytes:
    return _multi_page(
        [
            (
                "Q4 results (Finance only)",
                "Q4 revenue was 4.2 million USD. "
                "Gross margin was 61 percent. "
                "Deferred revenue remaining is 880000 USD. "
                "The largest customer concentration is 18 percent of ARR.",
            ),
            (
                "Next-quarter plan (Finance only)",
                "Headcount is frozen until 1 February except for backfills. "
                "The marketing budget for next quarter is 210000 USD. "
                "The bad debt reserve is 45000 USD. "
                "The board meeting pack is due on 12 January.",
            ),
        ]
    )


def _security_pdf() -> bytes:
    return _multi_page(
        [
            (
                "Incident intake",
                "Security incidents must be reported to security@docwise.example within one hour. "
                "When an incident is suspected, the on-call engineer freezes deployments and opens a ticket. "
                "Screenshots and timestamps are required for every report.",
            ),
            (
                "Containment",
                "If credentials are exposed, rotate them immediately and invalidate active sessions. "
                "The security lead can request a temporary access freeze for any affected account. "
                "Do not forward incident details outside the security channel.",
            ),
            (
                "Postmortem",
                "A postmortem is due within five business days after containment. "
                "Each postmortem lists the root cause, blast radius, remediation owner, and verification step. "
                "Track follow-up items in the security backlog until closed.",
            ),
            (
                "Contact matrix",
                "Primary security contact: security lead. "
                "Backup contact: platform on-call. "
                "For vendor issues, route through procurement only after the security lead has acknowledged the incident.",
            ),
        ]
    )


def _recruiting_pdf() -> bytes:
    doc = fitz.open()
    page1 = _add_page(
        doc,
        "Recruiting FAQ (HR only)",
        "Interview feedback must be entered within twenty four hours. "
        "Candidate compensation bands are hidden from non-HR staff. "
        "Interview panels use a three-point score: hire, lean hire, no hire.",
    )
    _draw_table(
        page1,
        origin=(72, 220),
        col_widths=[150.0, 120.0, 140.0],
        row_h=22.0,
        cells=[
            ["Stage", "Owner", "Target"],
            ["Screen", "Recruiter", "2 days"],
            ["Onsite", "Hiring manager", "5 days"],
            ["Offer", "HR", "1 day"],
        ],
    )
    _add_page(
        doc,
        "Offer process (HR only)",
        "Offers require approval from HR and the hiring manager. "
        "Once approved, the recruiter sends the offer letter, closes the requisition, and updates the tracker. "
        "Rejected candidates are archived after thirty days.",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _travel_pdf() -> bytes:
    doc = fitz.open()
    page1 = _add_page(
        doc,
        "Business travel policy",
        "Travel above 500 USD requires manager approval. "
        "Airfare should be booked at least seven days before departure. "
        "Per diem for domestic travel is 45 USD per day and 75 USD for international travel.",
    )
    _draw_table(
        page1,
        origin=(72, 220),
        col_widths=[150.0, 110.0, 130.0],
        row_h=22.0,
        cells=[
            ["Item", "Domestic", "International"],
            ["Hotel cap", "180 USD", "240 USD"],
            ["Meal cap", "25 USD", "35 USD"],
            ["Taxi cap", "40 USD", "60 USD"],
        ],
    )
    _add_page(
        doc,
        "Receipts and exceptions",
        "Receipts must be attached within five business days after the trip. "
        "Alcohol is never reimbursable. "
        "Extended stays need an explanation if the total hotel cost exceeds the nightly cap. "
        "The travel team can approve one exception per quarter.",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _it_access_checklist_pdf() -> bytes:
    return _multi_page(
        [
            (
                "Before day one",
                "Create the employee account, assign laptop serial number, and provision MFA. "
                "The recruiter sends the start date, home address, and phone number to IT only after the offer is signed. "
                "Badge pickup is coordinated with facilities.",
            ),
            (
                "Day one checklist",
                "Install password manager, Slack, and VPN. "
                "Set the default printer, configure GitHub SSO, and verify access to email, calendar, and time tracking. "
                "If any access is missing, open a helpdesk ticket immediately.",
            ),
            (
                "First week",
                "Check that the laptop is encrypted, backups run overnight, and the user knows how to reset MFA. "
                "The checklist closes only after the onboarding buddy confirms the account works in all required systems.",
            ),
        ]
    )


def _operations_handbook_pdf() -> bytes:
    return _multi_page(
        [
            (
                "Operating model",
                "Operations runs on three support zones: business hours, after-hours, and emergency. "
                "During business hours, the service desk owns requests; after-hours issues route to the on-call lead. "
                "Emergency changes require a follow-up note within one business day.",
            ),
            (
                "Release cadence",
                "Weekly releases land on Thursday after the change freeze lifts. "
                "Every release note records the owner, rollback steps, and the user-facing impact. "
                "Hotfixes are allowed only if a production incident is active or a customer-facing blocker is confirmed.",
            ),
            (
                "Change control",
                "Standard changes need one approver, normal changes need two approvers, and high-risk changes need an incident review first. "
                "Each change ticket includes scope, rollback plan, testing evidence, and a comms owner.",
            ),
            (
                "Vendor support",
                "Vendor outages are tracked in the support backlog. "
                "The vendor owner updates status twice per day until resolved. "
                "If a vendor misses the SLA twice in a quarter, the account is escalated to procurement.",
            ),
            (
                "Data handling",
                "Operational logs are retained for thirty days, audit exports for one year, and incident notes for two years. "
                "Do not paste customer secrets into chat. "
                "Shared screenshots must blur personal data before upload.",
            ),
            (
                "Weekly checklist",
                "Review the support queue, verify backups, close stale incidents, and confirm the on-call calendar. "
                "The checklist is complete only after the ownership board is updated and the release manager signs off.",
            ),
        ]
    )


def _people_compendium_pdf() -> bytes:
    doc = fitz.open()
    page1 = _add_page(
        doc,
        "People compendium (HR only)",
        "The people team owns promotions, compensation reviews, policy exceptions, and employee relations. "
        "Salary conversations are confidential and are never shared outside HR. "
        "Hiring managers receive only the minimum data required for their process.",
    )
    _draw_table(
        page1,
        origin=(72, 220),
        col_widths=[140.0, 110.0, 150.0],
        row_h=22.0,
        cells=[
            ["Topic", "Owner", "Cadence"],
            ["Comp review", "HRBP", "Twice yearly"],
            ["Promotion", "People partner", "Monthly"],
            ["Offer approval", "HR", "Daily"],
        ],
    )
    _add_page(
        doc,
        "Benefits and leave (HR only)",
        "Benefit questions are answered with the latest policy memo, not memory. "
        "The people team publishes a monthly FAQ for exceptions, parental leave, and bereavement leave. "
        "Only HR can edit benefit policy text.",
    )
    _add_page(
        doc,
        "Performance and calibration",
        "Calibration notes are stored in a separate workspace. "
        "Every review cycle ends with a calibration meeting, a manager follow-up, and a documentation sweep. "
        "HR keeps a list of approved rating exceptions for audit.",
    )
    _add_page(
        doc,
        "Offer workflow",
        "Compensation bands are checked before an offer is drafted. "
        "The recruiter sends the draft to HR, HR validates it against the band, and the hiring manager confirms the level. "
        "If the band is outside range, the offer is returned for revision.",
    )
    _add_page(
        doc,
        "Employee relations",
        "Sensitive cases are handled by the people partner and legal counsel. "
        "The case log records date, owner, action, and next step. "
        "Escalations remain confidential until the case is closed.",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _multi_page(pages: list[tuple[str, str]]) -> bytes:
    doc = fitz.open()
    for title, body in pages:
        _add_page(doc, title, body)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _add_page(doc: fitz.Document, title: str, body: str) -> fitz.Page:
    page = doc.new_page(width=A4[0], height=A4[1])
    page.insert_text((72, 72), title, fontsize=18, fontname="helv")
    page.insert_textbox(fitz.Rect(72, 100, 523, 420), body, fontsize=11, fontname="helv")
    return page


def _add_page_sections(doc: fitz.Document, sections: list[tuple[str, str]]) -> fitz.Page:
    """Multiple section headings on one physical page (chunker splits on headings)."""
    page = doc.new_page(width=A4[0], height=A4[1])
    y = 72.0
    for title, body in sections:
        page.insert_text((72, y), title, fontsize=18, fontname="helv")
        y += 30.0
        box = fitz.Rect(72, y, 523, min(y + 120.0, 780.0))
        page.insert_textbox(box, body, fontsize=11, fontname="helv")
        y = box.y1 + 28.0
    return page


def _draw_table(
    page: fitz.Page,
    *,
    origin: tuple[float, float],
    col_widths: list[float],
    row_h: float,
    cells: list[list[str]],
) -> None:
    x0, y0 = origin
    n_rows = len(cells)
    width = sum(col_widths)
    height = n_rows * row_h
    x1, y1 = x0 + width, y0 + height
    for row_i in range(n_rows + 1):
        y = y0 + row_i * row_h
        page.draw_line(fitz.Point(x0, y), fitz.Point(x1, y), color=(0, 0, 0), width=1.0)
    x = x0
    page.draw_line(fitz.Point(x0, y0), fitz.Point(x0, y1), color=(0, 0, 0), width=1.0)
    for col_w in col_widths:
        x += col_w
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y1), color=(0, 0, 0), width=1.0)
    for row_i, row in enumerate(cells):
        x = x0
        for col_i, value in enumerate(row):
            page.insert_text(
                (x + 6, y0 + row_i * row_h + 15),
                value,
                fontsize=10,
                fontname="helv",
            )
            x += col_widths[col_i]
