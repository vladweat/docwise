"""Mount `/api/v1` resource routers (auth, corpus, chat, billing, SSO)."""

from fastapi import APIRouter

from app.api import API_V1
from app.api.v1.auth import router as auth_router
from app.api.v1.billing import router as billing_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.domains import router as domains_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.search import router as search_router
from app.api.v1.sso import admin_router as sso_admin_router
from app.api.v1.sso import public_router as sso_public_router

api_router = APIRouter(prefix=API_V1)
api_router.include_router(auth_router)
api_router.include_router(sso_public_router)
api_router.include_router(organizations_router)
api_router.include_router(sso_admin_router)
api_router.include_router(domains_router)
api_router.include_router(billing_router)
api_router.include_router(documents_router)
api_router.include_router(chat_router)
api_router.include_router(search_router)

__all__ = ["API_V1", "api_router"]
