"""Backblaze B2 storage + playback-link tests (no network: boto3 is faked)."""
import boto3

from app.api.routes import stream
from app.core.config import settings
from app.services import storage
from app.services.transcode_service import BITRATE_LADDER, TranscodeService


class FakeS3:
    def __init__(self):
        self.uploads = []

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        self.uploads.append((bucket, key, ExtraArgs["ContentType"], ExtraArgs.get("CacheControl")))

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://signed.example/{Params['Bucket']}/{Params['Key']}?exp={ExpiresIn}"


def _configure(monkeypatch, public_url=""):
    monkeypatch.setattr(settings, "B2_ENDPOINT", "https://s3.us-east-005.backblazeb2.com")
    monkeypatch.setattr(settings, "B2_KEY_ID", "k")
    monkeypatch.setattr(settings, "B2_APP_KEY", "s")
    monkeypatch.setattr(settings, "B2_REGION", "")
    monkeypatch.setattr(settings, "B2_BUCKET", "bazzyvideo")
    monkeypatch.setattr(settings, "B2_PUBLIC_URL", public_url)
    storage._client.cache_clear()


def test_client_reads_region_from_endpoint(monkeypatch):
    _configure(monkeypatch)
    made = {}
    monkeypatch.setattr(boto3, "client", lambda svc, **kw: made.update(kw) or FakeS3())
    storage._client()
    assert made["region_name"] == "us-east-005"
    assert made["aws_secret_access_key"] == "s"
    storage._client.cache_clear()


def test_upload_dir_sets_types_and_caching(tmp_path, monkeypatch):
    _configure(monkeypatch)
    fake = FakeS3()
    monkeypatch.setattr(storage, "_client", lambda: fake)
    (tmp_path / "720p").mkdir()
    (tmp_path / "master.m3u8").write_text("#EXTM3U\n720p/index.m3u8\n")
    (tmp_path / "720p" / "index.m3u8").write_text("#EXTM3U\nseg00000.ts\n")
    (tmp_path / "720p" / "seg00000.ts").write_bytes(b"\x47" * 188)

    assert storage.upload_dir(tmp_path, "titles/t1") == 3
    assert sorted(fake.uploads) == [
        ("bazzyvideo", "titles/t1/720p/index.m3u8", "application/vnd.apple.mpegurl", "no-cache"),
        ("bazzyvideo", "titles/t1/720p/seg00000.ts", "video/mp2t", "public, max-age=31536000, immutable"),
        ("bazzyvideo", "titles/t1/master.m3u8", "application/vnd.apple.mpegurl", "no-cache"),
    ]


def test_segments_use_cdn_when_public_url_set(monkeypatch):
    _configure(monkeypatch, public_url="https://bazzyvideo.b-cdn.net/")
    assert storage.segment_url("titles/t1/720p/seg00000.ts") == "https://bazzyvideo.b-cdn.net/titles/t1/720p/seg00000.ts"


def test_segments_presigned_when_no_cdn(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(storage, "_client", lambda: FakeS3())
    url = storage.segment_url("titles/t1/720p/seg00000.ts")
    assert url.startswith("https://signed.example/bazzyvideo/titles/t1/720p/seg00000.ts?exp=")


def test_playlist_rewrite(monkeypatch):
    _configure(monkeypatch, public_url="https://cdn.test")
    master = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=3000000\n720p/index.m3u8\n"
    assert stream.rewrite_playlist(master, "t1", "master.m3u8", "TOK").splitlines()[-1] == \
        "/api/v1/stream/t1/720p/index.m3u8?t=TOK"
    child = "#EXTM3U\n#EXTINF:6.0,\nseg00000.ts\n#EXT-X-ENDLIST\n"
    lines = stream.rewrite_playlist(child, "t1", "720p/index.m3u8", "TOK").splitlines()
    assert lines[2] == "https://cdn.test/titles/t1/720p/seg00000.ts"
    assert lines[3] == "#EXT-X-ENDLIST"


def test_master_playlist_uses_relative_paths(tmp_path):
    svc = TranscodeService(work_root=str(tmp_path / "work"))
    rungs = [r for r in BITRATE_LADDER if r["height"] <= 720]
    svc._write_master_playlist(tmp_path, rungs)
    text = (tmp_path / "master.m3u8").read_text()
    assert "720p/index.m3u8" in text and "/tmp" not in text
    assert "4k" not in text and "1080p" not in text
