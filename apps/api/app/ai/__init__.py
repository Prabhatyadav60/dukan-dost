from functools import lru_cache

from ..config import get_settings


@lru_cache
def get_llm():
    if get_settings().ai_provider == "live":
        from .claude import ClaudeLLM
        return ClaudeLLM()
    from .fake import FakeLLM
    return FakeLLM()


@lru_cache
def get_stt():
    s = get_settings()
    if s.sarvam_api_key:  # real speech-to-text whenever a key is configured
        from .sarvam import SarvamSTT
        return SarvamSTT()
    from .fake import FakeSTT
    return FakeSTT()


@lru_cache
def get_tts():
    """Read-aloud needs a Sarvam key; without one the endpoint reports itself unavailable."""
    if get_settings().sarvam_api_key:
        from .sarvam import SarvamTTS
        return SarvamTTS()
    return None
