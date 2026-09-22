"""Private MinIO/S3 storage. Bytes leave the cluster only through the API."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DOCUMENTS_BUCKET = "documents"


class StorageError(RuntimeError):
    pass


def s3_endpoint_parts(url: str) -> tuple[str, bool]:
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    if not host:
        raise StorageError("S3_ENDPOINT is empty")
    return host, parsed.scheme == "https"


def object_key_for_document(document_id: UUID, filename: str, *, organization_id: UUID) -> str:
    """S3 key prefix includes org id so objects never share a flat global namespace."""
    safe_name = Path(filename).name or "document.pdf"
    return f"orgs/{organization_id}/{document_id}/{safe_name}"


def policy_allows_anonymous_read(policy_json: str) -> bool:
    try:
        policy = json.loads(policy_json)
    except json.JSONDecodeError:
        return False
    for statement in policy.get("Statement") or []:
        if str(statement.get("Effect", "")).lower() != "allow":
            continue
        principal = statement.get("Principal", {})
        if not _principal_is_anonymous(principal):
            continue
        actions = statement.get("Action") or []
        if isinstance(actions, str):
            actions = [actions]
        if any(action in {"s3:GetObject", "s3:*", "*"} for action in actions):
            return True
    return False


def _principal_is_anonymous(principal: object) -> bool:
    if principal == "*":
        return True
    if isinstance(principal, dict):
        aws = principal.get("AWS", principal.get("*"))
        if aws == "*":
            return True
        if isinstance(aws, list) and "*" in aws:
            return True
    return False


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        host, secure = s3_endpoint_parts(settings.s3_endpoint)
        self.bucket = settings.s3_bucket or DOCUMENTS_BUCKET
        self._client = Minio(
            host,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=secure,
        )

    def ensure_private_bucket(self) -> None:
        if not self._client.bucket_exists(self.bucket):
            self._client.make_bucket(self.bucket)
            logger.info("Created MinIO bucket %s", self.bucket)
        self._strip_public_policy()

    def bucket_is_ready(self) -> bool:
        if not self._client.bucket_exists(self.bucket):
            return False
        try:
            policy = self._client.get_bucket_policy(self.bucket)
        except S3Error as exc:
            if exc.code in {"NoSuchBucketPolicy", "NoSuchBucket"}:
                return exc.code == "NoSuchBucketPolicy"
            raise
        return not policy_allows_anonymous_read(policy)

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        try:
            self._client.put_object(
                self.bucket,
                key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        except S3Error as exc:
            raise StorageError(f"put_object failed: {exc.code}") from exc

    def get_bytes(self, key: str) -> bytes:
        try:
            response = self._client.get_object(self.bucket, key)
        except S3Error as exc:
            raise StorageError(f"get_object failed: {exc.code}") from exc
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_object(self, key: str) -> None:
        try:
            self._client.remove_object(self.bucket, key)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return
            raise StorageError(f"delete_object failed: {exc.code}") from exc

    def _strip_public_policy(self) -> None:
        try:
            policy = self._client.get_bucket_policy(self.bucket)
        except S3Error as exc:
            if exc.code in {"NoSuchBucketPolicy", "NoSuchBucket"}:
                return
            raise
        if policy_allows_anonymous_read(policy):
            self._client.delete_bucket_policy(self.bucket)
            logger.warning("Removed anonymous-read policy from bucket %s", self.bucket)


def get_object_storage() -> ObjectStorage:
    return ObjectStorage()


def ensure_documents_bucket() -> None:
    """Create a private `documents` bucket. Do not fail API startup if MinIO is down."""
    try:
        get_object_storage().ensure_private_bucket()
    except Exception as exc:
        logger.warning("MinIO bucket setup skipped: %s", exc)
