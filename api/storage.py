"""Document and photo storage.

S3-compatible storage (Railway Buckets) is used when a bucket and credentials
are configured. Otherwise files land on ``UPLOAD_DIR``, which must be a
persistent volume. Title scans stay private: downloads go through the API,
not a public object URL.
"""
import json
import os
import re
import uuid

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,180}$")
_MAX_BYTES = 25 * 1024 * 1024


def max_bytes() -> int:
    return _MAX_BYTES


def _first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def backend_name() -> str:
    explicit = os.environ.get("STORAGE_BACKEND", "").strip().lower()
    if explicit in ("s3", "volume"):
        return explicit
    if _bucket() and _access_key() and _secret_key():
        return "s3"
    return "volume"


def _bucket() -> str:
    return _first("S3_BUCKET", "AWS_S3_BUCKET_NAME", "BUCKET")


def _access_key() -> str:
    return _first("S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID", "ACCESS_KEY_ID")


def _secret_key() -> str:
    return _first("S3_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY", "SECRET_ACCESS_KEY")


def _endpoint() -> str:
    return _first("S3_ENDPOINT", "AWS_ENDPOINT_URL", "AWS_S3_ENDPOINT", "ENDPOINT")


def _region() -> str:
    region = _first("S3_REGION", "AWS_DEFAULT_REGION", "AWS_REGION", "REGION") or "us-east-1"
    if region.lower() == "auto":
        return "us-east-1"
    return region


def upload_dir() -> str:
    return os.path.abspath(os.environ.get("UPLOAD_DIR", "/data/uploads"))


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "upload.bin")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip(".-")
    return (cleaned or "upload.bin")[:80]


def _new_key(filename: str) -> str:
    return f"{uuid.uuid4().hex}-{_safe_filename(filename)}"


def _check_key(key: str) -> str:
    if not key or not _KEY_RE.match(key) or ".." in key:
        raise ValueError("invalid file key")
    return key


def _s3_client():
    import boto3
    from botocore.config import Config

    if not (_bucket() and _access_key() and _secret_key()):
        raise RuntimeError("object storage bucket or credentials are not set")
    kwargs = {
        "aws_access_key_id": _access_key(),
        "aws_secret_access_key": _secret_key(),
        "region_name": _region(),
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    endpoint = _endpoint()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def _object_key(key: str) -> str:
    prefix = os.environ.get("S3_PREFIX", "uploads").strip("/")
    return f"{prefix}/{key}" if prefix else key


def save_upload(filename: str, data: bytes, content_type: str) -> dict:
    if not data:
        raise ValueError("empty file")
    if len(data) > _MAX_BYTES:
        raise ValueError("file exceeds 25MB")
    key = _new_key(filename)
    content_type = content_type or "application/octet-stream"
    kind = backend_name()
    if kind == "s3":
        client = _s3_client()
        client.put_object(
            Bucket=_bucket(),
            Key=_object_key(key),
            Body=data,
            ContentType=content_type,
            Metadata={"filename": _safe_filename(filename)},
        )
    else:
        root = upload_dir()
        os.makedirs(root, exist_ok=True)
        path = os.path.join(root, key)
        meta = os.path.join(root, key + ".meta.json")
        with open(path, "wb") as handle:
            handle.write(data)
        with open(meta, "w", encoding="utf-8") as handle:
            json.dump(
                {"content_type": content_type, "filename": _safe_filename(filename)},
                handle,
            )
        os.chmod(path, 0o600)
    print(f"webclaw: stored upload bytes={len(data)} backend={kind}", flush=True)
    return {
        "status": "ok",
        "key": key,
        "url": f"/api/v1/files/{key}",
        "backend": kind,
        "bytes": len(data),
        "content_type": content_type,
    }


def open_upload(key: str) -> tuple[bytes, str, str]:
    key = _check_key(key)
    kind = backend_name()
    if kind == "s3":
        client = _s3_client()
        obj = client.get_object(Bucket=_bucket(), Key=_object_key(key))
        data = obj["Body"].read()
        content_type = obj.get("ContentType") or "application/octet-stream"
        filename = (obj.get("Metadata") or {}).get("filename") or key
        return data, content_type, filename
    root = upload_dir()
    path = os.path.realpath(os.path.join(root, key))
    if not path.startswith(os.path.realpath(root) + os.sep):
        raise ValueError("invalid file key")
    if not os.path.isfile(path):
        raise FileNotFoundError(key)
    with open(path, "rb") as handle:
        data = handle.read()
    content_type = "application/octet-stream"
    filename = key
    meta_path = path + ".meta.json"
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as handle:
                meta = json.load(handle)
            content_type = meta.get("content_type") or content_type
            filename = meta.get("filename") or filename
        except (OSError, json.JSONDecodeError):
            pass
    return data, content_type, filename
