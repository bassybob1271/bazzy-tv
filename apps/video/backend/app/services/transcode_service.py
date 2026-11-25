"""Bazzy Video — Transcode Pipeline Service
OCI Compute GPU → FFmpeg → HLS adaptive ladder → Cloudflare Stream
Ladder: 4K → 1080p → 720p → 480p → 360p
Codec: H.264 (now) + AV1 (Y3 target, 60% catalog)
"""
import subprocess
import os
import uuid
import mimetypes
import re
from pathlib import Path
from app.core.config import settings
from app.models.models import Title, ContentStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update


# HLS bitrate ladder
BITRATE_LADDER = [
    {"name": "4k",    "width": 3840, "height": 2160, "bitrate": "15000k", "audio": "320k"},
    {"name": "1080p", "width": 1920, "height": 1080, "bitrate": "5000k",  "audio": "192k"},
    {"name": "720p",  "width": 1280, "height": 720,  "bitrate": "2800k",  "audio": "128k"},
    {"name": "480p",  "width": 854,  "height": 480,  "bitrate": "1400k",  "audio": "128k"},
    {"name": "360p",  "width": 640,  "height": 360,  "bitrate": "800k",   "audio": "96k"},
]


class TranscodeService:

    def __init__(self):
        self.work_dir = Path("/tmp/bazzy-transcode")
        self.work_dir.mkdir(exist_ok=True)

    async def ingest_and_transcode(self, db: AsyncSession, title_id: str,
                                    master_path: str) -> str:
        """
        Full pipeline:
        1. Validate master file
        2. Extract metadata (duration, resolution, audio)
        3. Transcode to HLS adaptive ladder
        4. Upload segments to OCI hot bucket
        5. Push to Cloudflare Stream
        6. Generate thumbnail sprites
        7. Update title record
        Returns: HLS manifest URL
        """
        job_dir = self.work_dir / title_id
        job_dir.mkdir(exist_ok=True)

        # Step 1: Probe master
        probe = self._ffprobe(master_path)
        duration_s = int(float(probe.get("duration", 0)))
        runtime_minutes = max(1, duration_s // 60)

        # Step 2: Transcode each rung
        hls_outputs = []
        for rung in BITRATE_LADDER:
            out_dir = job_dir / rung["name"]
            out_dir.mkdir(exist_ok=True)
            self._transcode_rung(master_path, str(out_dir), rung)
            hls_outputs.append((rung["name"], str(out_dir / "index.m3u8")))

        # Step 3: Master playlist
        master_playlist = self._build_master_playlist(hls_outputs, job_dir)

        # Step 4: Upload to OCI
        oci_base_url = await self._upload_media(title_id, job_dir)

        # Step 5: Push to Cloudflare Stream CDN
        cf_uid = await self._push_to_cloudflare_stream(master_playlist)

        # Step 6: Thumbnail sprites
        await self._generate_sprites(master_path, title_id, duration_s)

        # Step 7: Update DB
        hls_url = f"https://videodelivery.net/{cf_uid}/manifest/video.m3u8"
        await db.execute(
            update(Title)
            .where(Title.id == title_id)
            .values(
                cf_stream_uid=cf_uid,
                hls_manifest_url=hls_url,
                runtime_minutes=runtime_minutes,
                status=ContentStatus.REVIEW,
            )
        )
        await db.commit()
        return hls_url

    def _ffprobe(self, path: str) -> dict:
        """Extract media metadata via ffprobe."""
        import json
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", path
        ], capture_output=True, text=True)
        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        return {"duration": fmt.get("duration", 0)}

    def _transcode_rung(self, input_path: str, out_dir: str, rung: dict):
        """Transcode single bitrate rung to HLS segments."""
        cmd = [
            "ffmpeg", "-i", input_path, "-y",
            # Video
            "-vf", f"scale={rung['width']}:{rung['height']}",
            "-c:v", "libx264", "-b:v", rung["bitrate"],
            "-preset", "slow", "-profile:v", "high",
            # Audio
            "-c:a", "aac", "-b:a", rung["audio"],
            # HLS output
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", f"{out_dir}/seg%05d.ts",
            f"{out_dir}/index.m3u8",
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    def _build_master_playlist(self, hls_outputs: list, job_dir: Path) -> str:
        """Build HLS master playlist referencing all rungs."""
        lines = ["#EXTM3U", "#EXT-X-VERSION:3", ""]
        bw_map = {"4k": 15000000, "1080p": 5000000, "720p": 2800000,
                   "480p": 1400000, "360p": 800000}
        res_map = {"4k": "3840x2160", "1080p": "1920x1080", "720p": "1280x720",
                    "480p": "854x480", "360p": "640x360"}
        for name, path in hls_outputs:
            lines.append(f'#EXT-X-STREAM-INF:BANDWIDTH={bw_map[name]},RESOLUTION={res_map[name]}')
            lines.append(path)
        master_path = str(job_dir / "master.m3u8")
        with open(master_path, "w") as f:
            f.write("\n".join(lines))
        return master_path

    async def _upload_media(self, title_id: str, job_dir: Path) -> str:
        if settings.STORAGE_BACKEND.lower() == "oci":
            return await self._upload_to_oci(title_id, job_dir)
        return await self._upload_to_b2(title_id, job_dir)

    async def _upload_to_b2(self, title_id: str, job_dir: Path) -> str:
        """Upload HLS output to the Backblaze B2 bucket (S3 API). Returns the public base URL."""
        import asyncio
        import boto3
        from boto3.s3.transfer import TransferConfig

        if not (settings.B2_ENDPOINT and settings.B2_KEY_ID and settings.B2_APP_KEY):
            raise RuntimeError("Set B2_ENDPOINT, B2_KEY_ID and B2_APP_KEY to store video on Backblaze B2")
        m = re.search(r"s3\.([a-z0-9-]+)\.backblazeb2\.com", settings.B2_ENDPOINT)
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.B2_ENDPOINT,
            region_name=settings.B2_REGION or (m.group(1) if m else "us-east-1"),
            aws_access_key_id=settings.B2_KEY_ID,
            aws_secret_access_key=settings.B2_APP_KEY,
        )
        base_path = f"titles/{title_id}"
        transfer = TransferConfig(multipart_threshold=64 * 1024 * 1024, multipart_chunksize=64 * 1024 * 1024)

        def put_all():
            for file in job_dir.rglob("*"):
                if not file.is_file():
                    continue
                rel = file.relative_to(job_dir).as_posix()
                playlist = rel.endswith(".m3u8")
                ctype = "application/vnd.apple.mpegurl" if playlist else (
                    "video/mp2t" if rel.endswith(".ts") else mimetypes.guess_type(rel)[0] or "application/octet-stream")
                s3.upload_file(str(file), settings.B2_BUCKET, f"{base_path}/{rel}", Config=transfer, ExtraArgs={
                    "ContentType": ctype,
                    "CacheControl": "public, max-age=60" if playlist else "public, max-age=31536000, immutable",
                })

        await asyncio.to_thread(put_all)
        public = settings.B2_PUBLIC_URL.rstrip("/") or f"{settings.B2_ENDPOINT.rstrip('/')}/{settings.B2_BUCKET}"
        return f"{public}/{base_path}"

    async def _upload_to_oci(self, title_id: str, job_dir: Path) -> str:
        """Upload HLS segments to OCI Object Storage hot bucket."""
        # In production: use OCI SDK upload_manager for parallel multipart
        # Simplified here — real implementation uses asyncio + OCI SDK
        import oci

        config = oci.config.from_file()
        object_storage = oci.object_storage.ObjectStorageClient(config)
        namespace = settings.OCI_NAMESPACE
        bucket = settings.OCI_BUCKET_HOT
        base_path = f"titles/{title_id}"

        for file in job_dir.rglob("*"):
            if file.is_file():
                rel = str(file.relative_to(job_dir))
                with open(file, "rb") as f:
                    object_storage.put_object(namespace, bucket, f"{base_path}/{rel}", f)

        return f"https://objectstorage.{settings.OCI_REGION}.oraclecloud.com/n/{namespace}/b/{bucket}/o/{base_path}"

    async def _push_to_cloudflare_stream(self, master_playlist_path: str) -> str:
        """Upload master HLS manifest to Cloudflare Stream. Returns CF UID."""
        # Cloudflare Stream: POST /accounts/{id}/stream/copy or direct upload
        import httpx
        with open(master_playlist_path, "rb") as f:
            resp = httpx.post(
                f"https://api.cloudflare.com/client/v4/accounts/{settings.CF_ACCOUNT_ID}/stream",
                headers={
                    "Authorization": f"Bearer {settings.CF_STREAM_TOKEN}",
                    "Tus-Resumable": "1.0.0",
                },
                content=f.read(),
            )
        return resp.json().get("result", {}).get("uid", str(uuid.uuid4()))

    async def _generate_sprites(self, master_path: str, title_id: str, duration_s: int):
        """Generate thumbnail sprite sheet for scrubbing preview."""
        out_dir = self.work_dir / title_id / "sprites"
        out_dir.mkdir(exist_ok=True)
        interval = max(10, duration_s // 100)
        subprocess.run([
            "ffmpeg", "-i", master_path, "-y",
            "-vf", f"fps=1/{interval},scale=160:90,tile=10x10",
            str(out_dir / "sprite.jpg"),
        ], capture_output=True)
