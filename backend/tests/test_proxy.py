import os

from app.core.proxy import apply_internal_no_proxy


def test_apply_internal_no_proxy_keeps_minio(monkeypatch):
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1,130.100.7.0/24")
    monkeypatch.setenv("NO_PROXY", "localhost")
    apply_internal_no_proxy()
    assert "minio" in os.environ["NO_PROXY"].split(",")
    assert "postgres" in os.environ["no_proxy"].split(",")
    assert "qdrant" not in os.environ["no_proxy"].split(",")
    assert "slither" not in os.environ["no_proxy"].split(",")
    assert "130.100.7.0/24" in os.environ["no_proxy"]
