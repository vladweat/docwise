from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_infra_lives_in_core_not_utils():
    assert not (ROOT / "app" / "utils").exists()
    import app.core.logging  # noqa: F401
    import app.core.rate_limit  # noqa: F401
    import app.core.redis  # noqa: F401


def test_celery_lives_in_worker():
    assert not (ROOT / "app" / "celery_config.py").exists()
    from worker.celery_app import celery_app, process_document_task

    assert process_document_task.name == "ingestion.process_document"
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_time_limit == 25 * 60
    assert celery_app.conf.task_soft_time_limit == 20 * 60
    assert process_document_task.max_retries == 3


def test_compose_uses_minio_latest():
    here = Path(__file__).resolve()
    compose = next(
        (
            candidate
            for candidate in (
                here.parents[2] / "docker-compose.yml",
                ROOT.parent / "docker-compose.yml",
            )
            if candidate.is_file()
        ),
        None,
    )
    if compose is None:
        pytest.skip("docker-compose.yml is not mounted in this environment")
    text = compose.read_text()
    assert "image: minio/minio:latest" in text


def test_dockerfile_does_not_ship_tests():
    text = (ROOT / "Dockerfile").read_text()
    assert "COPY tests" not in text
    assert "COPY worker ./worker" in text


def test_service_modules_match_api_resources():
    assert (ROOT / "app/services/documents.py").is_file()
    assert not (ROOT / "app/services/document_service.py").exists()
    assert (ROOT / "app/services/search.py").is_file()
    assert not (ROOT / "app/services/inspect.py").exists()
    assert (ROOT / "app/services/chat.py").is_file()
    assert (ROOT / "app/services/chat_sessions.py").is_file()
    assert (ROOT / "app/api/v1/auth").is_dir()
    assert (ROOT / "app/api/v1/auth/password.py").is_file()
    assert (ROOT / "app/api/v1/auth/issue.py").is_file()
    assert not (ROOT / "app/api/v1/session.py").exists()


def test_services_do_not_raise_http_exception():
    for path in (ROOT / "app/services").rglob("*.py"):
        source = path.read_text()
        assert "HTTPException" not in source, path


def test_models_are_split_by_aggregate():
    import app.models.chat as chat_mod
    import app.models.organization as org_mod
    from app.models.audit import RagAuditLog
    from app.models.billing import BillingStatus
    from app.models.domain import OrganizationDomain
    from app.models.sso import OrganizationSsoConnection

    assert not hasattr(org_mod, "BillingStatus")
    assert not hasattr(org_mod, "OrganizationSsoConnection")
    assert not hasattr(org_mod, "OrganizationDomain")
    assert not hasattr(chat_mod, "RagAuditLog")
    assert RagAuditLog.__tablename__ == "rag_audit_logs"
    assert BillingStatus.active.value == "active"
    assert OrganizationSsoConnection.__tablename__ == "organization_sso_connections"
    assert OrganizationDomain.__tablename__ == "organization_domains"


def test_foreign_organization_id_is_not_a_billing_schema():
    import app.schemas.billing as billing_schemas
    from app.schemas.common import foreign_organization_id

    assert callable(foreign_organization_id)
    assert not hasattr(billing_schemas, "foreign_organization_id")


def test_sso_http_lives_in_one_module():
    from app.api.v1.sso import admin_router, public_router

    public_paths = {route.path for route in public_router.routes}
    admin_paths = {route.path for route in admin_router.routes}
    assert "/auth/sso/{slug}/login" in public_paths
    assert "/auth/sso/{slug}/acs" in public_paths
    assert "/organizations/sso" in admin_paths


def test_package_docstrings_describe_the_layer():
    import app.schemas
    import app.services

    assert "Object storage" not in (app.services.__doc__ or "")
    assert "resource module" in (app.schemas.__doc__ or "")
    assert "Domain services" in (app.services.__doc__ or "")


def test_engine_uses_explicit_pool_settings():
    from app.core.config import get_settings
    from app.core.database import engine

    settings = get_settings()
    assert engine.pool.size() == settings.db_pool_size
    assert engine.pool._max_overflow == settings.db_max_overflow
    assert settings.db_pool_size >= 1
    assert settings.db_max_overflow >= 0
