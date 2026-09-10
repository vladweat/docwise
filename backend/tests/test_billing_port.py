"""M6b: billing port (dev / stripe). No live api.stripe.com."""

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import time
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.billing import BillingEvent, BillingProvider
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.organization import BillingStatus, Organization, OrganizationStatus
from app.services.billing import billing_readiness, get_billing_port
from app.services.billing.stripe_adapter import StripeBillingPort
from app.services.quotas import QUOTA_EXCEEDED
from helpers import make_org, register_payload, wipe_app_tables

MIN_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
WHSEC = "whsec_test_docwise"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/pdf") -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        from app.services.storage import StorageError

        if key not in self.objects:
            raise StorageError("missing")
        return self.objects[key]

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)


@pytest.fixture(autouse=True)
def clean_tables():
    db: Session = SessionLocal()
    wipe_app_tables(db)
    db.close()
    yield
    db = SessionLocal()
    wipe_app_tables(db)
    db.close()


@pytest.fixture(autouse=True)
def _mock_celery(monkeypatch):
    monkeypatch.setattr("app.services.document_service.enqueue_ingestion", lambda document_id: None)


def _unique_email(prefix: str = "bill") -> str:
    return f"{prefix}-{uuid4().hex[:8]}@example.com"


def _register(name: str, password: str = "securepass123") -> tuple[TestClient, str]:
    http = TestClient(app)
    email = _unique_email(name.lower().replace(" ", ""))
    response = http.post(
        "/api/v1/auth/register",
        json=register_payload(email, password, organization_name=name),
    )
    assert response.status_code == 201
    return http, email


def _org_id(http: TestClient) -> UUID:
    return UUID(http.get("/api/v1/auth/me").json()["organization_id"])


def _set_stripe_env(monkeypatch, *, secret: str = "sk_test_x", webhook: str = WHSEC) -> None:
    monkeypatch.setenv("BILLING_PROVIDER", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", secret)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", webhook)
    monkeypatch.setenv("STRIPE_PRICE_TEAM", "price_team")
    get_settings.cache_clear()


def _sign(payload: bytes, secret: str = WHSEC, ts: int | None = None) -> str:
    timestamp = str(ts if ts is not None else int(time.time()))
    digest = hmac.new(secret.encode("utf-8"), timestamp.encode("utf-8") + b"." + payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_quotas_module_does_not_call_billing_provider():
    from app.services import quotas

    source = inspect.getsource(quotas)
    assert "get_billing_port" not in source
    assert "stripe" not in source.lower()
    assert "BILLING_PROVIDER" not in source


def test_subscription_exposes_dev_provider():
    http, _ = _register("Acme")
    sub = http.get("/api/v1/billing/subscription")
    assert sub.status_code == 200
    assert sub.json()["provider"] == "dev"
    assert sub.json()["plan"] == "starter"


def test_dev_change_plan_writes_postgres_not_other_org():
    acme, _ = _register("Acme")
    globex, _ = _register("Globex")
    globex_org = _org_id(globex)
    response = acme.post(
        "/api/v1/billing/plan",
        json={"plan": "team", "organization_id": str(globex_org)},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
    db = SessionLocal()
    assert db.get(Organization, globex_org).plan == "starter"
    assert db.get(Organization, _org_id(acme)).plan == "starter"
    db.close()

    changed = acme.post("/api/v1/billing/plan", json={"plan": "enterprise"})
    assert changed.status_code == 200
    body = changed.json()
    assert body["provider"] == "dev"
    assert body["plan"] == "enterprise"
    assert body["entitlements"]["sso"] is True
    db = SessionLocal()
    acme_org = db.get(Organization, _org_id(acme))
    other = db.get(Organization, globex_org)
    assert acme_org.plan == "enterprise"
    assert other.plan == "starter"
    events = db.query(BillingEvent).filter(BillingEvent.organization_id == acme_org.id).all()
    assert len(events) == 1
    assert events[0].provider == BillingProvider.dev.value
    assert "chunk" not in json.dumps(events[0].payload).lower()
    db.close()


def test_simulate_set_plan_and_foreign_org_is_404():
    acme, _ = _register("Acme")
    globex, _ = _register("Globex")
    globex_id = _org_id(globex)
    blocked = acme.post(
        "/api/v1/billing/dev/simulate",
        json={"action": "set_plan", "plan": "enterprise", "organization_id": str(globex_id)},
    )
    assert blocked.status_code == 404
    assert blocked.json()["detail"] == "Not Found"
    db = SessionLocal()
    assert db.get(Organization, globex_id).plan == "starter"
    assert db.get(Organization, globex_id).status == OrganizationStatus.active.value
    db.close()

    ok = acme.post(
        "/api/v1/billing/dev/simulate",
        json={"action": "set_plan", "plan": "team"},
    )
    assert ok.status_code == 200
    assert ok.json()["plan"] == "team"
    assert ok.json()["provider"] == "dev"


def test_employee_simulate_is_404():
    admin, _ = _register("Acme")
    email = _unique_email("emp")
    invited = admin.post(
        "/api/v1/organizations/invites",
        json={"email": email, "role": "employee", "departments": []},
    )
    assert invited.status_code == 201
    employee = TestClient(app)
    registered = employee.post(
        "/api/v1/auth/register",
        json=register_payload(email, invite_token=invited.json()["invite_token"]),
    )
    assert registered.status_code == 201
    response = employee.post("/api/v1/billing/dev/simulate", json={"action": "cancel"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"


def test_simulate_unauthenticated_is_401():
    response = TestClient(app).post("/api/v1/billing/dev/simulate", json={"action": "cancel"})
    assert response.status_code == 401


def test_past_due_and_cancel_suspend_org_login():
    http, email = _register("Acme")
    org_id = _org_id(http)
    due = http.post("/api/v1/billing/dev/simulate", json={"action": "past_due"})
    assert due.status_code == 200
    assert due.json()["billing_status"] == "past_due"
    db = SessionLocal()
    org = db.get(Organization, org_id)
    assert org.status == OrganizationStatus.suspended.value
    assert org.billing_status == BillingStatus.past_due.value
    db.close()
    assert http.get("/api/v1/auth/me").status_code == 401
    login = TestClient(app).post("/api/v1/auth/login", json={"email": email, "password": "securepass123"})
    assert login.status_code == 403
    assert login.json()["detail"] == "Organization is suspended"

    http2, _ = _register("Globex")
    globex_id = _org_id(http2)
    cancel = http2.post("/api/v1/billing/dev/simulate", json={"action": "cancel"})
    assert cancel.status_code == 200
    db = SessionLocal()
    globex = db.get(Organization, globex_id)
    assert globex.status == OrganizationStatus.suspended.value
    assert globex.billing_status == BillingStatus.canceled.value
    db.close()


def test_simulate_disabled_when_provider_is_stripe(monkeypatch):
    http, _ = _register("Acme")
    _set_stripe_env(monkeypatch, secret="", webhook="")
    response = http.post("/api/v1/billing/dev/simulate", json={"action": "cancel"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"


def test_stripe_without_keys_ready_and_plan_503(monkeypatch):
    http, _ = _register("Acme")
    _set_stripe_env(monkeypatch, secret="", webhook="")
    assert billing_readiness() == "error"
    ready = http.get("/ready")
    assert ready.json()["billing"] == "error"
    assert ready.json()["status"] == "degraded"
    assert ready.status_code == 503
    plan = http.post("/api/v1/billing/plan", json={"plan": "team"})
    assert plan.status_code == 503
    hook = http.post("/api/v1/billing/webhooks/stripe", content=b"{}")
    assert hook.status_code == 404
    usage = http.get("/api/v1/billing/usage")
    assert usage.status_code == 200
    assert usage.json()["plan"] == "starter"


def test_stripe_plan_returns_checkout_url_without_live_api(monkeypatch):
    http, _ = _register("Acme")
    _set_stripe_env(monkeypatch)
    monkeypatch.setattr(
        StripeBillingPort,
        "_create_checkout_session",
        lambda self, org, plan, price_id: "https://checkout.stripe.com/c/test",
    )
    response = http.post("/api/v1/billing/plan", json={"plan": "team"})
    assert response.status_code == 200
    assert response.json()["checkout_url"] == "https://checkout.stripe.com/c/test"
    db = SessionLocal()
    org = db.get(Organization, _org_id(http))
    assert org.plan == "starter"
    db.close()


def test_quotas_still_work_when_stripe_provider(monkeypatch):
    from app.api.documents import get_storage

    monkeypatch.setenv("PLAN_STARTER_PAGES", "1")
    _set_stripe_env(monkeypatch, secret="", webhook="")
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    try:
        acme, _ = _register("Acme")
        globex, _ = _register("Globex")
        db = SessionLocal()
        db.add(
            Document(
                organization_id=_org_id(acme),
                title="Full.pdf",
                file_path="full.pdf",
                file_hash="ab" * 32,
                file_size_bytes=8,
                total_pages=1,
                access_roles=["all"],
                status=DocumentStatus.ready.value,
            )
        )
        db.commit()
        db.close()
        blocked = acme.post(
            "/api/v1/documents/upload",
            files={"file": ("over.pdf", MIN_PDF, "application/pdf")},
            data={"access_roles": ["all"]},
        )
        assert blocked.status_code == 402
        assert blocked.json()["detail"] == QUOTA_EXCEEDED
        allowed = globex.post(
            "/api/v1/documents/upload",
            files={"file": ("ok.pdf", MIN_PDF.replace(b"%%EOF", b"%g\n%%EOF"), "application/pdf")},
            data={"access_roles": ["all"]},
        )
        assert allowed.status_code == 201
    finally:
        app.dependency_overrides.pop(get_storage, None)


def test_stripe_webhook_payment_failed_suspends_and_is_idempotent(monkeypatch):
    http, email = _register("Acme")
    org_id = _org_id(http)
    _set_stripe_env(monkeypatch)
    db = SessionLocal()
    org = db.get(Organization, org_id)
    org.stripe_customer_id = "cus_acme"
    db.commit()
    db.close()

    payload = json.dumps(
        {
            "id": "evt_pay_fail_1",
            "type": "invoice.payment_failed",
            "data": {"object": {"id": "in_1", "customer": "cus_acme", "subscription": "sub_acme"}},
        }
    ).encode()
    headers = {"stripe-signature": _sign(payload)}
    first = TestClient(app).post("/api/v1/billing/webhooks/stripe", content=payload, headers=headers)
    assert first.status_code == 200
    assert first.json() == {"received": True}
    db = SessionLocal()
    org = db.get(Organization, org_id)
    assert org.billing_status == BillingStatus.past_due.value
    assert org.status == OrganizationStatus.suspended.value
    assert db.query(BillingEvent).filter(BillingEvent.external_id == "evt_pay_fail_1").count() == 1
    chunks = db.query(DocumentChunk).count()
    assert chunks == 0
    db.close()

    second = TestClient(app).post("/api/v1/billing/webhooks/stripe", content=payload, headers=headers)
    assert second.status_code == 200
    db = SessionLocal()
    assert db.query(BillingEvent).filter(BillingEvent.external_id == "evt_pay_fail_1").count() == 1
    db.close()

    login = TestClient(app).post("/api/v1/auth/login", json={"email": email, "password": "securepass123"})
    assert login.status_code == 403

    paid = json.dumps(
        {
            "id": "evt_paid_1",
            "type": "invoice.paid",
            "data": {"object": {"id": "in_2", "customer": "cus_acme", "subscription": "sub_acme"}},
        }
    ).encode()
    TestClient(app).post(
        "/api/v1/billing/webhooks/stripe",
        content=paid,
        headers={"stripe-signature": _sign(paid)},
    )
    db = SessionLocal()
    org = db.get(Organization, org_id)
    assert org.status == OrganizationStatus.active.value
    assert org.billing_status == BillingStatus.active.value
    db.close()
    restored = TestClient(app).post("/api/v1/auth/login", json={"email": email, "password": "securepass123"})
    assert restored.status_code == 200


def test_stripe_webhook_invalid_signature(monkeypatch):
    http, _ = _register("Acme")
    _set_stripe_env(monkeypatch)
    payload = b'{"id":"evt_x","type":"invoice.paid","data":{"object":{}}}'
    response = http.post(
        "/api/v1/billing/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert response.status_code == 400


def test_stripe_webhook_on_dev_provider_is_404():
    response = TestClient(app).post("/api/v1/billing/webhooks/stripe", content=b"{}")
    assert response.status_code == 404


def test_webhook_does_not_read_corpus(monkeypatch):
    source = inspect.getsource(StripeBillingPort.handle_webhook)
    assert "DocumentChunk" not in source
    assert "document_chunks" not in source
    module = inspect.getsource(inspect.getmodule(StripeBillingPort))
    assert "DocumentChunk" not in module
    assert "from app.models.document" not in module


def test_dev_default_readiness():
    from app.services.billing.dev import DevBillingPort

    assert get_settings().billing_provider_name == "dev"
    assert billing_readiness() == "dev"
    assert isinstance(get_billing_port(), DevBillingPort)


def test_make_org_helper_still_inserts():
    db = SessionLocal()
    org = make_org(db)
    db.commit()
    assert org.plan == "starter"
    db.close()
