import hashlib

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import Field

from .. import clock
from ..ai import get_tts
from ..auth import repo_dep
from ..db import MerchantScopedRepo
from ..errors import AppError
from ..models import Strict

router = APIRouter(prefix="/v1")


class TtsReq(Strict):
    text: str = Field(min_length=1, max_length=600)


@router.post("/tts", response_class=Response)
async def tts(req: TtsReq, repo: MerchantScopedRepo = Depends(repo_dep)):
    """Speak an assistant message. Cached per text, so replaying a bubble costs nothing."""
    engine = get_tts()
    if engine is None:
        raise AppError("tts_unavailable", 503, "Awaaz abhi available nahi hai.")
    text = " ".join(req.text.split())
    key = hashlib.sha256(text.encode()).hexdigest()
    cached = await repo.find_one("tts_cache", {"text_hash": key})
    if cached:
        audio = bytes(cached["audio"])
    else:
        audio = await engine.speak(text)
        await repo.insert("tts_cache", {"text_hash": key, "audio": audio, "created_at": clock.now()})
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=86400"})
