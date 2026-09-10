from fastapi.testclient import TestClient

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
