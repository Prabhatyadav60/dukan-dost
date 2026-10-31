"""Upload checks by magic bytes, audio normalisation via ffmpeg, image storage outside the web root."""
import asyncio
import os
import tempfile
import uuid
from pathlib import Path

from ..config import get_settings
from ..errors import AppError

IMAGE_MAGIC = {b"\xff\xd8\xff": ("image/jpeg", "jpg"), b"\x89PNG": ("image/png", "png")}
MAX_IMAGE = 5 * 1024 * 1024
MAX_AUDIO = 2 * 1024 * 1024
MAX_AUDIO_SECONDS = 30


def sniff_image(data: bytes) -> tuple[str, str]:
    if len(data) > MAX_IMAGE:
        raise AppError("file_too_large", 413, "Photo 5 MB se chhoti honi chahiye.")
    for magic, kind in IMAGE_MAGIC.items():
        if data.startswith(magic):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    raise AppError("unsupported_media", 415, "Sirf JPEG, PNG ya WebP photo chalegi.")


def save_image(merchant_id: str, folder: str, data: bytes, ext: str) -> str:
    key = f"{folder}/{merchant_id}/{uuid.uuid4().hex}.{ext}"
    path = Path(get_settings().upload_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def load_image(key: str) -> bytes:
    return (Path(get_settings().upload_dir) / key).read_bytes()


def _audio_ok(data: bytes) -> bool:
    return (data[:4] in (b"\x1aE\xdf\xa3", b"OggS", b"RIFF", b"fLaC") or data[4:8] == b"ftyp"
            or data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"))


async def _run(*args: str) -> tuple[int, bytes]:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.DEVNULL)
    out, _ = await proc.communicate()
    return proc.returncode or 0, out


def ffmpeg_bin() -> str:
    """Bundled static ffmpeg (imageio-ffmpeg), so a broken system install can't break voice entry."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return "ffmpeg"


async def to_wav(data: bytes) -> str:
    """Validate and convert to 16 kHz mono WAV. Caller deletes the returned temp file."""
    if len(data) > MAX_AUDIO:
        raise AppError("file_too_large", 413, "Audio 2 MB se chhota hona chahiye.")
    if not _audio_ok(data):
        raise AppError("unsupported_media", 415, "Yeh audio format nahi chalega.")
    src = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
    src.write(data)
    src.close()
    dst = src.name + ".wav"
    try:
        # convert one second past the limit so over-long clips are detectable from the output length
        code, _ = await _run(ffmpeg_bin(), "-y", "-v", "error", "-i", src.name, "-t", str(MAX_AUDIO_SECONDS + 1),
                             "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", dst)
        if code != 0 or not os.path.exists(dst):
            raise AppError("unsupported_media", 415, "Audio padh nahi paaye.")
        seconds = (os.path.getsize(dst) - 44) / (16000 * 2)
        if seconds > MAX_AUDIO_SECONDS + 0.5:
            os.unlink(dst)
            raise AppError("audio_too_long", 422, "30 second se chhota bolein.")
        return dst
    finally:
        os.unlink(src.name)
