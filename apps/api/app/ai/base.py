from typing import Protocol

from .schemas import BillDraft, EntryDraft, ShelfResult


class Image(Protocol):
    media_type: str
    data: bytes


class SpeechToText(Protocol):
    async def transcribe(self, wav_path: str, original_name: str) -> str: ...


class LLM(Protocol):
    async def parse_entry(self, transcript: str) -> EntryDraft: ...
    async def read_bill(self, images: list[tuple[str, bytes]]) -> BillDraft: ...
    async def write_reminder(self, payload: dict) -> str: ...
    async def write_explanation(self, payload: dict) -> str: ...
    async def compare_shelf(self, before: tuple[str, bytes] | None, after: tuple[str, bytes]) -> ShelfResult: ...
