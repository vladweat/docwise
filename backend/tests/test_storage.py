"""MinIO object storage upload and delete."""

from unittest.mock import MagicMock
from uuid import uuid4

from minio.error import S3Error

from app.services.storage import (
    ObjectStorage,
    object_key_for_document,
    policy_allows_anonymous_read,
    s3_endpoint_parts,
)

PUBLIC_GET_POLICY = """
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"AWS": ["*"]},
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::documents/*"]
    }
  ]
}
"""


def _s3_error(code: str) -> S3Error:
    return S3Error(
        code=code,
        message=code,
        resource="/documents",
        request_id="req",
        host_id="host",
        response=MagicMock(),
    )


def test_s3_endpoint_parts_strip_scheme():
    host, secure = s3_endpoint_parts("http://minio:9000")
    assert host == "minio:9000"
    assert secure is False
    host, secure = s3_endpoint_parts("https://s3.example.com")
    assert host == "s3.example.com"
    assert secure is True


def test_object_key_stays_under_org_and_document_prefix():
    org_id = uuid4()
    doc_id = uuid4()
    key = object_key_for_document(doc_id, "../../secret.pdf", organization_id=org_id)
    assert key == f"orgs/{org_id}/{doc_id}/secret.pdf"
    assert ".." not in key


def test_policy_detects_anonymous_get():
    assert policy_allows_anonymous_read(PUBLIC_GET_POLICY) is True
    assert policy_allows_anonymous_read("{}") is False


def test_ensure_private_bucket_strips_public_policy(monkeypatch):
    client = MagicMock()
    client.bucket_exists.return_value = False
    client.get_bucket_policy.return_value = PUBLIC_GET_POLICY
    monkeypatch.setattr("app.services.storage.Minio", lambda *args, **kwargs: client)

    storage = ObjectStorage()
    storage.ensure_private_bucket()

    client.make_bucket.assert_called_once_with("documents")
    client.delete_bucket_policy.assert_called_once_with("documents")


def test_bucket_is_ready_when_private(monkeypatch):
    client = MagicMock()
    client.bucket_exists.return_value = True
    client.get_bucket_policy.side_effect = _s3_error("NoSuchBucketPolicy")
    monkeypatch.setattr("app.services.storage.Minio", lambda *args, **kwargs: client)

    assert ObjectStorage().bucket_is_ready() is True


def test_bucket_is_not_ready_when_public(monkeypatch):
    client = MagicMock()
    client.bucket_exists.return_value = True
    client.get_bucket_policy.return_value = PUBLIC_GET_POLICY
    monkeypatch.setattr("app.services.storage.Minio", lambda *args, **kwargs: client)

    assert ObjectStorage().bucket_is_ready() is False


def test_delete_object_ignores_missing_key(monkeypatch):
    client = MagicMock()
    client.remove_object.side_effect = _s3_error("NoSuchKey")
    monkeypatch.setattr("app.services.storage.Minio", lambda *args, **kwargs: client)
    ObjectStorage().delete_object("gone.pdf")
    client.remove_object.assert_called_once()


def test_put_bytes_does_not_set_public_acl(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("app.services.storage.Minio", lambda *args, **kwargs: client)

    ObjectStorage().put_bytes("abc/file.pdf", b"%PDF-1.4", content_type="application/pdf")
    kwargs = client.put_object.call_args.kwargs
    assert "acl" not in kwargs
    assert "metadata" not in kwargs or "public" not in str(kwargs.get("metadata")).lower()


def test_storage_module_has_no_public_url_helpers():
    import app.services.storage as storage

    names = {name.lower() for name in dir(storage)}
    assert not any("presign" in name or "public_url" in name for name in names)
    assert not hasattr(ObjectStorage, "get_public_url")
    assert not hasattr(ObjectStorage, "presigned_get_object")
