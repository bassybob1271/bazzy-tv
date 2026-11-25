import asyncio

import boto3

from app.core.config import settings
from app.services.transcode_service import TranscodeService


def test_uploads_hls_to_b2(tmp_path, monkeypatch):
    (tmp_path / "720p").mkdir()
    (tmp_path / "master.m3u8").write_text("#EXTM3U")
    (tmp_path / "720p" / "seg0.ts").write_bytes(b"\x47" * 188)
    calls, made = [], {}

    class Fake:
        def upload_file(self, path, bucket, key, Config=None, ExtraArgs=None):
            calls.append((bucket, key, ExtraArgs["ContentType"], ExtraArgs["CacheControl"]))

    def client(service, **kw):
        made.update(kw)
        return Fake()

    monkeypatch.setattr(boto3, "client", client)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "b2")
    monkeypatch.setattr(settings, "B2_ENDPOINT", "https://s3.us-east-005.backblazeb2.com")
    monkeypatch.setattr(settings, "B2_KEY_ID", "k")
    monkeypatch.setattr(settings, "B2_APP_KEY", "s")
    monkeypatch.setattr(settings, "B2_BUCKET", "BazzyVideo")
    monkeypatch.setattr(settings, "B2_PUBLIC_URL", "https://bazzyvideo.b-cdn.net/")

    svc = TranscodeService.__new__(TranscodeService)
    url = asyncio.run(svc._upload_media("t1", tmp_path))

    assert url == "https://bazzyvideo.b-cdn.net/titles/t1"
    assert made["region_name"] == "us-east-005"
    assert sorted(calls) == [
        ("BazzyVideo", "titles/t1/720p/seg0.ts", "video/mp2t", "public, max-age=31536000, immutable"),
        ("BazzyVideo", "titles/t1/master.m3u8", "application/vnd.apple.mpegurl", "public, max-age=60"),
    ]
