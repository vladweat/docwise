from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db, require_admin
from app.models.document import DocumentStatus
from app.models.user import User
from app.schemas.document import (
    DocumentAccessUpdate,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
)
from app.services.document_service import (
    create_document_from_upload,
    delete_document,
    document_pdf_bytes,
    document_status,
    list_documents,
    update_document_access_roles,
)
from app.services.storage import ObjectStorage, get_object_storage
from app.utils.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/documents", tags=["documents"])


def get_storage() -> ObjectStorage:
    return get_object_storage()


def require_upload_admin(current_user: User = Depends(require_admin)) -> User:
    enforce_rate_limit("upload", str(current_user.id), get_settings().rate_limit_upload_per_minute)
    return current_user


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF (admin)",
    description="Requires admin. Duplicate SHA-256 returns 409 without the existing document.",
)
async def upload_document(
    file: Annotated[UploadFile, File()],
    access_roles: list[str] = Form(default_factory=list),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_upload_admin),
    storage: ObjectStorage = Depends(get_storage),
) -> DocumentResponse:
    _ = current_user
    content = await file.read()
    document = create_document_from_upload(
        db,
        filename=file.filename or "document.pdf",
        content=content,
        content_type=file.content_type,
        access_roles_raw=access_roles,
        storage=storage,
    )
    return document


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents visible to the caller",
)
def list_documents_endpoint(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    return list_documents(
        db,
        current_user,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Ingestion status",
    responses={404: {"description": "Missing or not visible to the caller"}},
)
def get_document_status(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentStatusResponse:
    return document_status(db, current_user, document_id)


@router.get(
    "/{document_id}/raw",
    summary="PDF bytes",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "Missing or not visible to the caller"},
    },
)
def get_document_raw(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_storage),
) -> Response:
    data, title = document_pdf_bytes(db, current_user, document_id, storage=storage)
    safe_title = "".join(ch for ch in title if ch not in '"\\\r\n')[:180] or "document.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_title}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document ACL (admin)",
    description="Requires admin. Copies access_roles onto every chunk in the same transaction.",
    responses={404: {"description": "Document row is missing"}},
)
def patch_document_access(
    document_id: UUID,
    payload: DocumentAccessUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DocumentResponse:
    _ = current_user
    return update_document_access_roles(db, document_id, payload)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document (admin)",
    description="Requires admin. Cascades Postgres rows (document + chunks) and the MinIO object.",
)
def delete_document_endpoint(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    storage: ObjectStorage = Depends(get_storage),
) -> None:
    _ = current_user
    delete_document(db, document_id, storage=storage)
