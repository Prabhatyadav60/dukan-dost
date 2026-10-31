"""Sarvam speech to text (saaras:v3, hi-IN) over REST."""
import httpx

from ..config import get_settings
from . import calls

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"


class SarvamSTT:
    async def transcribe(self, wav_path: str, original_name: str) -> str:
        key = get_settings().sarvam_api_key

        async def once() -> str:
            async with httpx.AsyncClient() as client:
                with open(wav_path, "rb") as f:
                    r = await client.post(
                        SARVAM_STT_URL, headers={"api-subscription-key": key},
                        files={"file": ("audio.wav", f, "audio/wav")},
                        data={"model": "saaras:v3", "mode": "transcribe", "language_code": "hi-IN"})
            r.raise_for_status()
            return r.json()["transcript"]

        return await calls.call("sarvam", "speech", once)
