from fastapi.testclient import TestClient

from app.api import API_V1
from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "docwise-backend"


def test_health_is_liveness_only():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_unversioned():
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code in {200, 503}
    assert client.get(f"{API_V1}/health").status_code == 404
    assert client.get(f"{API_V1}/ready").status_code == 404


def test_resource_api_is_mounted_at_api_v1():
    assert API_V1 == "/api/v1"
    assert client.get(f"{API_V1}/auth/me").status_code == 401


def test_ready_checks_dependencies():
    response = client.get("/ready")
    assert response.status_code in {200, 503}
    data = response.json()
    assert "status" in data
    assert "postgres" in data
    assert "redis" in data
    assert "pgvector" in data
    assert "minio" in data
    assert "billing" in data
    assert data["billing"] in {"dev", "ok", "error"}
    assert "qdrant" not in data
    assert "slither" not in data
