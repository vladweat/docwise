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

DEFAULT_EVAL_EMAIL = "eval-employee@docwise.local"
DEFAULT_EVAL_PASSWORD = "eval-employee-pass"

RESTRICTED_DOC_IDS = (str(HR_COMP_ID), str(FINANCE_ID))


@dataclass(frozen=True)
class FixtureSpec:
    id: UUID
    slug: str
    filename: str
    access_roles: tuple[str, ...]
    builder: str


CATALOG: tuple[FixtureSpec, ...] = (
    FixtureSpec(HANDBOOK_ID, "employee-handbook", "Employee-Handbook.pdf", ("all",), "handbook"),
    FixtureSpec(LEAVE_ID, "leave-policy", "Leave-Policy.pdf", ("all",), "leave"),
    FixtureSpec(EXPENSE_ID, "expense-policy", "Expense-Policy.pdf", ("all",), "expense"),
    FixtureSpec(ENGINEERING_ID, "engineering-onboarding", "Engineering-Onboarding.pdf", ("all",), "engineering"),
    FixtureSpec(HR_COMP_ID, "hr-compensation", "HR-Compensation.pdf", ("hr",), "hr_comp"),
    FixtureSpec(FINANCE_ID, "finance-q4", "Finance-Q4-Memo.pdf", ("finance",), "finance"),
)

CATALOG_BY_ID = {str(item.id): item for item in CATALOG}


def restricted_doc_ids() -> tuple[str, ...]:
    return RESTRICTED_DOC_IDS


def build_pdf(spec: FixtureSpec) -> bytes:
    builders = {
        "handbook": _handbook_pdf,
        "leave": _leave_pdf,
        "expense": _expense_pdf,
        "engineering": _engineering_pdf,
        "hr_comp": _hr_comp_pdf,
        "finance": _finance_pdf,
    }
    return builders[spec.builder]()


def seed_corpus(*, email: str | None = None, password: str | None = None) -> dict:
    """Upsert fixture PDFs and the employee eval user, then run real `index_pdf`."""
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.models.document import Document, DocumentStatus
    from app.models.user import User, UserRole
    from app.services.ingestion import delete_chunks_for_document, index_pdf
    from app.services.storage import get_object_storage, object_key_for_document

    eval_email = (email or os.environ.get("EVAL_USER_EMAIL") or DEFAULT_EVAL_EMAIL).strip()
    eval_password = password or os.environ.get("EVAL_USER_PASSWORD") or DEFAULT_EVAL_PASSWORD

    db = SessionLocal()
    storage = get_object_storage()
    storage.ensure_private_bucket()
    indexed: list[dict] = []
    try:
        user = db.query(User).filter(User.email == eval_email).first()
        if user is None:
            user = User(
                email=eval_email,
                hashed_password=hash_password(eval_password),
                role=UserRole.employee.value,
                departments=[],
                is_active=True,
            )
            db.add(user)
            logger.info("created eval user %s", eval_email)
        else:
            user.role = UserRole.employee.value
            user.departments = []
            user.is_active = True
            if not user.hashed_password:
                user.hashed_password = hash_password(eval_password)
            logger.info("reset eval user %s to employee with no departments", eval_email)
        db.commit()

        for spec in CATALOG:
            pdf_bytes = build_pdf(spec)
            digest = hashlib.sha256(pdf_bytes).hexdigest()
            conflict = (
                db.query(Document)
                .filter(Document.file_hash == digest, Document.id != spec.id)
                .first()
            )
            if conflict is not None:
                raise RuntimeError(
                    f"Eval fixture hash collides with existing document {conflict.id} ({conflict.title}). "
                    "Delete that row or skip seeding."
                )
            key = object_key_for_document(spec.id, spec.filename)
            storage.put_bytes(key, pdf_bytes, content_type="application/pdf")
            document = db.get(Document, spec.id)
            if document is None:
                document = Document(
                    id=spec.id,
                    title=spec.filename,
                    file_path=key,
                    file_hash=digest,
                    file_size_bytes=len(pdf_bytes),
                    access_roles=list(spec.access_roles),
                    status=DocumentStatus.processing.value,
                )
                db.add(document)
            else:
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
        return {"eval_user_email": eval_email, "documents": indexed}
    finally:
        db.close()


def _handbook_pdf() -> bytes:
    return _multi_page(
        [
            (
                "Work schedule",
                "Core working hours at Docwise are 09:00 to 18:00 Europe/Moscow. "
                "The unpaid lunch break is 13:00 to 14:00. "
                "The hybrid policy requires office attendance on Tuesday, Wednesday, and Thursday; "
                "Monday and Friday are remote days. "
                "A desk must be booked in the Places portal before 17:00 on the previous day.",
            ),
            (
                "Code of conduct",
                "Employees must not store client personal data on personal devices. "
                "Security incidents must be emailed to security@docwise.example within one hour. "
                "External blog posts about the product require legal review before publishing. "
                "Gifts from vendors over 50 USD must be declined.",
            ),
            (
                "Equipment",
                "The standard laptop warranty is 36 months. "
                "A lost badge replacement fee is 15 USD after the first free replacement. "
                "Hardware requests go through Service Desk category IT / Hardware. "
                "Docking stations are issued only to employees with an assigned office desk.",
            ),
        ]
    )


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
    return _multi_page(
        [
            (
                "First week",
                "On day one, enable GitHub SSO via Okta and collect a laptop from the IT cage on floor 4. "
                "Each new hire is assigned a buddy for 30 days. "
                "Required reading is the employee handbook and the leave policy. "
                "The first pull request must be opened within five working days.",
            ),
            (
                "Delivery",
                "Staging deploys use make up on the staging cluster. "
                "Production deploys need two approvers from the on-call rotation. "
                "The default Python version is 3.12. "
                "The on-call starter rotation begins after 90 days.",
            ),
        ]
    )


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
