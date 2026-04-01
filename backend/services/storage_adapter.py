"""Storage adapter abstraction (Local + OSS)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import settings

_storage_metrics = {
    "read_failures": 0,
}


@dataclass
class StoredObject:
    provider: str
    object_key: str
    uri: str
    size_bytes: int


class BaseStorage:
    def put_bytes(self, *, object_key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        raise NotImplementedError

    def get_bytes(self, *, object_key: str) -> bytes:
        raise NotImplementedError

    def health_check(self) -> tuple[bool, str]:
        raise NotImplementedError


class LocalStorage(BaseStorage):
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, *, object_key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        target = self.base_dir / object_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return StoredObject(
            provider="local",
            object_key=object_key,
            uri=str(target.resolve()),
            size_bytes=len(data),
        )

    def get_bytes(self, *, object_key: str) -> bytes:
        target = self.base_dir / object_key
        return target.read_bytes()

    def health_check(self) -> tuple[bool, str]:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            return True, f"local:{self.base_dir}"
        except Exception as e:
            return False, str(e)


class OSSStorage(BaseStorage):
    def __init__(self):
        import oss2

        auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        self.bucket = oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket_name)

    def put_bytes(self, *, object_key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        self.bucket.put_object(object_key, data, headers=headers)
        uri = f"oss://{settings.oss_bucket_name}/{object_key}"
        return StoredObject(
            provider="oss",
            object_key=object_key,
            uri=uri,
            size_bytes=len(data),
        )

    def get_bytes(self, *, object_key: str) -> bytes:
        obj = self.bucket.get_object(object_key)
        return obj.read()

    def health_check(self) -> tuple[bool, str]:
        try:
            self.bucket.get_bucket_info()
            return True, f"oss:{settings.oss_bucket_name}@{settings.oss_endpoint}"
        except Exception as e:
            return False, str(e)


def build_object_key(*, project_id: str, task_id: str, filename: str) -> str:
    ext = ""
    if "." in filename:
        ext = filename[filename.rfind("."):]
    safe_name = filename.replace(" ", "_") if filename else "upload"
    day = datetime.utcnow().strftime("%Y%m%d")
    prefix = settings.oss_prefix.strip("/") or "unrealmake"
    return f"{prefix}/imports/{project_id}/{day}/{task_id}/{safe_name}{ext if not safe_name.endswith(ext) else ''}"


def mark_storage_read_failure() -> None:
    _storage_metrics["read_failures"] = _storage_metrics.get("read_failures", 0) + 1


def get_storage_metrics() -> dict:
    return dict(_storage_metrics)


def get_storage() -> BaseStorage:
    provider = (settings.storage_provider or "local").lower()
    if provider == "oss":
        return OSSStorage()
    return LocalStorage(settings.storage_local_dir)
