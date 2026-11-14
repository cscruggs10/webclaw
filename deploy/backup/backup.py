#!/usr/bin/env python3
"""Dump ERPClaw's Postgres database and store it in the uploads bucket.

The connection URL and object-storage secret are never printed. A missing
bucket is a failed run, so a cron tick cannot look healthy while the dump
only existed on the container's disk.
"""
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

_SECRET_URL = re.compile(
    r"(?i)\b(?:postgres(?:ql)?|mysql)://[^\s'\"\\]+"
)


def redact(text: str) -> str:
    return _SECRET_URL.sub(
        lambda match: match.group(0).split("://", 1)[0] + "://[redacted]",
        text or "",
    )


def first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def s3_client():
    import boto3
    from botocore.config import Config

    region = first("S3_REGION", "AWS_DEFAULT_REGION", "AWS_REGION", "REGION") or "us-east-1"
    if region.lower() == "auto":
        region = "us-east-1"
    kwargs = {
        "aws_access_key_id": first("S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID", "ACCESS_KEY_ID"),
        "aws_secret_access_key": first(
            "S3_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY", "SECRET_ACCESS_KEY"
        ),
        "region_name": region,
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    endpoint = first("S3_ENDPOINT", "AWS_ENDPOINT_URL", "AWS_S3_ENDPOINT", "ENDPOINT")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def main() -> None:
    url = (os.environ.get("DATABASE_URL") or os.environ.get("ERPCLAW_DB_URL") or "").strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith("postgresql://"):
        print("backup: DATABASE_URL is not a postgresql:// URL", file=sys.stderr)
        sys.exit(1)

    bucket = first("S3_BUCKET", "AWS_S3_BUCKET_NAME", "BUCKET")
    access = first("S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID", "ACCESS_KEY_ID")
    secret = first("S3_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY", "SECRET_ACCESS_KEY")
    require_s3 = os.environ.get("BACKUP_REQUIRE_S3", "1").lower() not in ("0", "false", "no")
    if not (bucket and access and secret):
        print("backup: object storage is not configured", file=sys.stderr)
        sys.exit(1 if require_s3 else 0)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = os.environ.get("BACKUP_PREFIX", "backups").strip("/")
    key = f"{prefix}/erpclaw-{stamp}.dump" if prefix else f"erpclaw-{stamp}.dump"

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "erpclaw.dump")
        proc = subprocess.run(
            ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", path, url],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print("backup: pg_dump failed", file=sys.stderr)
            print(redact(proc.stderr)[-2000:], file=sys.stderr)
            sys.exit(1)
        size = os.path.getsize(path)
        client = s3_client()
        with open(path, "rb") as handle:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=handle,
                ContentType="application/octet-stream",
            )
    print(f"backup: stored pg_dump bytes={size} key={key}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("backup: failed", file=sys.stderr)
        print(redact(str(exc))[-1000:], file=sys.stderr)
        sys.exit(1)
