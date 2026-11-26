"""Bazzy Video — Transcode pipeline
master upload → FFmpeg HLS adaptive ladder → Backblaze B2 (private bucket)
Ladder: 4K → 1080p → 720p → 480p → 360p (rungs above the source's height are skipped)
"""
import json
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Title, ContentStatus
from app.services import storage

BITRATE_LADDER = [
    {"name": "4k",    "width": 3840, "height": 2160, "bitrate": "15000k", "maxrate": "16000k", "audio": "320k", "bw": 15500000},
    {"name": "1080p", "width": 1920, "height": 1080, "bitrate": "5000k",  "maxrate": "5350k",  "audio": "192k", "bw": 5400000},
    {"name": "720p",  "width": 1280, "height": 720,  "bitrate": "2800k",  "maxrate": "3000k",  "audio": "128k", "bw": 3000000},
    {"name": "480p",  "width": 854,  "height": 480,  "bitrate": "1400k",  "maxrate": "1500k",  "audio": "128k", "bw": 1550000},
    {"name": "360p",  "width": 640,  "height": 360,  "bitrate": "800k",   "maxrate": "856k",   "audio": "96k",  "bw": 900000},
]


def hls_prefix(title_id: str) -> str:
    return f"titles/{title_id}"


class TranscodeService:

    def __init__(self, work_root: str = "/tmp/bazzy-transcode"):
        self.work_dir = Path(work_root)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    async def ingest_and_transcode(self, db: AsyncSession, title_id: str, master_path: str) -> str:
        """Transcode, upload to B2, mark the title ready for review.
        Returns the B2 key of the HLS master playlist (titles/<id>/master.m3u8)."""
        await db.execute(update(Title).where(Title.id == title_id).values(status=ContentStatus.PROCESSING))
        await db.commit()

        job_dir = self.work_dir / title_id
        shutil.rmtree(job_dir, ignore_errors=True)
        out = job_dir / "hls"
        out.mkdir(parents=True)
        try:
            probe = self._ffprobe(master_path)
            src_h = probe["height"] or 1080
            rungs = [r for r in BITRATE_LADDER if r["height"] <= max(src_h, 360)] or [BITRATE_LADDER[-1]]

            for rung in rungs:
                (out / rung["name"]).mkdir()
                self._transcode_rung(master_path, out / rung["name"], rung, probe["has_audio"])
            self._write_master_playlist(out, rungs)
            self._generate_sprites(master_path, out / "sprites", probe["duration"])

            # Archive the original, then publish the HLS tree.
            storage.upload_file(master_path, f"masters/{title_id}/{Path(master_path).name}")
            storage.upload_dir(out, hls_prefix(title_id))

            key = f"{hls_prefix(title_id)}/master.m3u8"
            await db.execute(
                update(Title).where(Title.id == title_id).values(
                    hls_manifest_url=key,              # B2 key; players get it via /api/v1/stream
                    runtime_minutes=max(1, int(probe["duration"]) // 60),
                    status=ContentStatus.REVIEW,
                )
            )
            await db.commit()
            return key
        except Exception:
            await db.execute(update(Title).where(Title.id == title_id).values(status=ContentStatus.PENDING))
            await db.commit()
            raise
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
            Path(master_path).unlink(missing_ok=True)

    # ── ffmpeg helpers ────────────────────────────────────────────────────
    def _ffprobe(self, path: str) -> dict:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                            "-show_streams", "-show_format", path],
                           capture_output=True, text=True, check=True)
        data = json.loads(r.stdout)
        v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        return {
            "duration": float(data.get("format", {}).get("duration") or 0),
            "height": int(v.get("height") or 0),
            "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", [])),
        }

    def _transcode_rung(self, src: str, out_dir: Path, rung: dict, has_audio: bool):
        cmd = [
            "ffmpeg", "-y", "-i", src,
            "-vf", f"scale=w={rung['width']}:h={rung['height']}:force_original_aspect_ratio=decrease,"
                   f"pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264", "-preset", "medium", "-profile:v", "high",
            "-b:v", rung["bitrate"], "-maxrate", rung["maxrate"], "-bufsize", rung["maxrate"],
            "-g", "48", "-keyint_min", "48", "-sc_threshold", "0",   # aligned keyframes across rungs
        ]
        cmd += ["-c:a", "aac", "-b:a", rung["audio"], "-ac", "2"] if has_audio else ["-an"]
        cmd += ["-hls_time", "6", "-hls_playlist_type", "vod",
                "-hls_segment_filename", str(out_dir / "seg%05d.ts"), str(out_dir / "index.m3u8")]
        subprocess.run(cmd, check=True, capture_output=True)

    def _write_master_playlist(self, out: Path, rungs: list):
        lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
        for r in rungs:   # paths are RELATIVE so the stream endpoint can rewrite them
            lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={r['bw']},RESOLUTION={r['width']}x{r['height']}")
            lines.append(f"{r['name']}/index.m3u8")
        (out / "master.m3u8").write_text("\n".join(lines) + "\n")

    def _generate_sprites(self, src: str, out_dir: Path, duration_s: float):
        out_dir.mkdir(exist_ok=True)
        interval = max(10, int(duration_s) // 100)
        subprocess.run(["ffmpeg", "-y", "-i", src, "-vf",
                        f"fps=1/{interval},scale=160:90,tile=10x10", "-frames:v", "1",
                        str(out_dir / "sprite.jpg")], capture_output=True)
