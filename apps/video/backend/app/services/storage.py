"""Bazzy Video — Backblaze B2 storage (S3-compatible API).

Layout in the bucket (default "bazzyvideo" — B2's S3 API wants the lowercase name):
  masters/<title_id>/<filename>        original uploads (archive)
  titles/<title_id>/master.m3u8        HLS master playlist
  titles/<title_id>/<rung>/index.m3u8  per-quality playlists
  titles/<title_id>/<rung>/segNNNNN.ts segments
  titles/<title_id>/sprites/sprite.jpg scrub thumbnails

Playback goes through /api/v1/stream/..., which checks the viewer's access and returns
playlists whose segment lines point at either
  • B2_PUBLIC_URL (a Bunny CDN pull zone in front of the bucket), when set, or
  • short-lived presigned B2 URLs, so the bucket can stay fully private.
"""
from __future__ import annotations

import mimetypes
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import settings


class StorageNotConfigured(RuntimeError):
    pass


CONTENT_TYPES = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
    ".m4s": "video/iso.segment",
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
}


def b2_configured() -> bool:
    return bool(settings.B2_KEY_ID and settings.B2_APP_KEY and settings.B2_ENDPOINT)


@lru_cache()
def _client():
    if not b2_configured():
        raise StorageNotConfigured(
            "Backblaze B2 isn't configured: set B2_KEY_ID, B2_APP_KEY and B2_ENDPOINT in .env"
        )
    endpoint = settings.B2_ENDPOINT if settings.B2_ENDPOINT.startswith("http") else f"https://{settings.B2_ENDPOINT}"
    # Region is the middle part of s3.<region>.backblazeb2.com
    m = re.search(r"s3\.([a-z0-9-]+)\.backblazeb2\.com", endpoint)
    region = settings.B2_REGION or (m.group(1) if m else "us-east-1")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=settings.B2_KEY_ID,
        aws_secret_access_key=settings.B2_APP_KEY,
        config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
    )


def bucket() -> str:
    return settings.B2_BUCKET


def _content_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    return CONTENT_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def upload_file(local_path: str | Path, key: str, cache_control: Optional[str] = None) -> str:
    """Upload one file (multipart automatically for large files). Returns the key."""
    extra = {"ContentType": _content_type(str(local_path))}
    if cache_control:
        extra["CacheControl"] = cache_control
    _client().upload_file(str(local_path), bucket(), key, ExtraArgs=extra)
    return key


def upload_dir(local_dir: str | Path, prefix: str) -> int:
    """Upload every file under local_dir to prefix/, keeping relative paths. Returns file count."""
    local_dir = Path(local_dir)
    n = 0
    for f in sorted(local_dir.rglob("*")):
        if f.is_file():
            rel = f.relative_to(local_dir).as_posix()
            # Segments never change; playlists may be re-published.
            cc = "public, max-age=31536000, immutable" if f.suffix in (".ts", ".m4s") else "no-cache"
            upload_file(f, f"{prefix}/{rel}", cache_control=cc)
            n += 1
    return n


def download_file(key: str, local_path: str | Path) -> None:
    _client().download_file(bucket(), key, str(local_path))


def read_text(key: str) -> str:
    obj = _client().get_object(Bucket=bucket(), Key=key)
    return obj["Body"].read().decode("utf-8")


def presigned_get(key: str, expires_s: Optional[int] = None) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket(), "Key": key},
        ExpiresIn=expires_s or settings.B2_URL_TTL_SECONDS,
    )


def segment_url(key: str) -> str:
    """Where players fetch a segment: the CDN when B2_PUBLIC_URL is set, else a presigned B2 link."""
    public = settings.B2_PUBLIC_URL.rstrip("/")
    return f"{public}/{key}" if public else presigned_get(key)


def delete_prefix(prefix: str) -> int:
    c, n = _client(), 0
    for page in c.get_paginator("list_objects_v2").paginate(Bucket=bucket(), Prefix=prefix):
        keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        if keys:
            c.delete_objects(Bucket=bucket(), Delete={"Objects": keys})
            n += len(keys)
    return n


def set_cors(origins: list[str]) -> None:
    """Allow the website's origins to GET segments directly from B2 (needed by hls.js)."""
    _client().put_bucket_cors(
        Bucket=bucket(),
        CORSConfiguration={"CORSRules": [{
            "AllowedOrigins": origins,
            "AllowedMethods": ["GET", "HEAD"],
            "AllowedHeaders": ["*"],
            "ExposeHeaders": ["Content-Length", "Content-Range", "ETag"],
            "MaxAgeSeconds": 3600,
        }]},
    )


def health() -> dict:
    """Round-trip check: bucket reachable, write, read, presign, delete."""
    if not b2_configured():
        return {"configured": False, "ok": False, "error": "B2 keys not set"}
    c, key = _client(), "_healthcheck/bazzy-video.txt"
    try:
        c.head_bucket(Bucket=bucket())
        c.put_object(Bucket=bucket(), Key=key, Body=b"ok", ContentType="text/plain")
        body = c.get_object(Bucket=bucket(), Key=key)["Body"].read()
        url = presigned_get(key, 60)
        c.delete_object(Bucket=bucket(), Key=key)
        return {"configured": True, "ok": body == b"ok", "bucket": bucket(),
                "endpoint": settings.B2_ENDPOINT, "presign_sample": url.split("?")[0],
                "delivery": "cdn " + settings.B2_PUBLIC_URL if settings.B2_PUBLIC_URL else "presigned B2 links"}
    except Exception as e:  # surfaced to the admin, not swallowed
        return {"configured": True, "ok": False, "bucket": bucket(), "error": f"{type(e).__name__}: {e}"}
