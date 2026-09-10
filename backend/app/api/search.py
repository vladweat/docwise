from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.core.principal import Principal
from app.models.user import UserRole
from app.schemas.search import SearchInspectRequest, SearchInspectResponse
from app.services.inspect import inspect_search
from app.services.retrieval import RetrievalError

router = APIRouter(prefix="/search", tags=["search"])

_NOT_FOUND = "Not Found"
_INSPECT_FAILED = "Search inspect failed"


def require_search_inspect(current_user: Principal = Depends(get_current_user)) -> Principal:
    if not get_settings().search_inspect_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    if current_user.role != UserRole.admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@router.post("/inspect", response_model=SearchInspectResponse)
def search_inspect(
    body: SearchInspectRequest,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_search_inspect),
) -> SearchInspectResponse:
    try:
        return inspect_search(db, current_user, body.query, limit=body.limit)
    except RetrievalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_INSPECT_FAILED,
        ) from exc
