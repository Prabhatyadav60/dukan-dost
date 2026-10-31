"""Sarvam speech to text (saaras:v3, hi-IN) over REST."""
import base64

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


SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


class SarvamTTS:
    """Sarvam Bulbul v3. Latin-script Hinglish goes in as-is: it is pronounced correctly
    (verified by round-tripping through STT), while transliterating first garbles words."""

    async def speak(self, text: str) -> bytes:
        key = get_settings().sarvam_api_key

        async def once() -> bytes:
            async with httpx.AsyncClient() as client:
                r = await client.post(SARVAM_TTS_URL, headers={"api-subscription-key": key},
                                      json={"text": text, "target_language_code": "hi-IN", "model": "bulbul:v3"})
            r.raise_for_status()
            return base64.b64decode(r.json()["audios"][0])

        return await calls.call("sarvam", "tts", once)
