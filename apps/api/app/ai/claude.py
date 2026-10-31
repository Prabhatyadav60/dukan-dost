"""Claude via the Anthropic SDK — direct API or Bedrock (Mantle). Structured outputs give schema-valid JSON."""
import base64
import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from ..config import get_settings
from . import calls
from .schemas import Answer, BillDraft, EntryDraft, Explanation, Message, ShelfResult

PROMPTS = Path(__file__).parent / "prompts"


def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text()


def _image(media_type: str, data: bytes) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.b64encode(data).decode()}}


class ClaudeLLM:
    def __init__(self):
        s = get_settings()
        if s.llm_backend == "bedrock":
            from anthropic import AsyncAnthropicBedrockMantle
            self.client = AsyncAnthropicBedrockMantle(aws_region=s.aws_region, max_retries=0)
            self.model, self.provider = s.bedrock_model_id, "bedrock"
        else:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=s.anthropic_api_key or None, max_retries=0)
            self.model, self.provider = s.claude_model, "anthropic"

    async def _structured(self, prompt: str, content: list[dict], schema: type[BaseModel], kind: str):
        async def once():
            resp = await self.client.messages.parse(
                model=self.model, max_tokens=4000, system=_prompt(prompt),
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": content}], output_format=schema)
            if resp.parsed_output is None:
                raise ValueError(f"no parsed output (stop_reason={resp.stop_reason})")
            return resp.parsed_output

        try:
            return await calls.call(self.provider, kind, once)
        except Exception as exc:
            if isinstance(exc.__cause__, (ValidationError, ValueError)):  # one repair retry
                return await calls.call(self.provider, kind, once)
            raise

    async def parse_entry(self, transcript: str, today: str) -> EntryDraft:
        text = f"Today: {today}\nMessage: {transcript}"
        return await self._structured("voice", [{"type": "text", "text": text}], EntryDraft, "text")

    async def ask(self, question: str, context: dict, history: list[dict]) -> str:
        payload = {"shop_data": context, "recent_conversation": history, "question": question}
        r = await self._structured("ask", [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                                   Answer, "vision")  # longer budget: bigger context than other text calls
        return r.answer

    async def read_bill(self, images) -> BillDraft:
        content = [_image(mt, b) for mt, b in images] + [{"type": "text", "text": "Read this bill."}]
        return await self._structured("bill", content, BillDraft, "vision")

    async def write_reminder(self, payload: dict) -> str:
        r = await self._structured("reminder", [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                                   Message, "text")
        return r.message

    async def write_explanation(self, payload: dict) -> str:
        r = await self._structured("explain", [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                                   Explanation, "text")
        return r.text

    async def compare_shelf(self, earlier: list[tuple[str, str, bytes]], today: tuple[str, bytes]) -> ShelfResult:
        """earlier: [(date, media_type, bytes)] oldest first; today: (media_type, bytes)."""
        content: list[dict] = []
        for d, mt, data in earlier:
            content += [{"type": "text", "text": f"Earlier photo, {d}:"}, _image(mt, data)]
        content += [{"type": "text", "text": "Today's photo:"}, _image(*today)]
        return await self._structured("shelf", content, ShelfResult, "vision")
