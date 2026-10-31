from .. import clock
from ..db import MerchantScopedRepo


async def add(repo: MerchantScopedRepo, role: str, kind: str, text: str, ref: dict | None = None) -> dict:
    return await repo.insert("thread_messages", {"role": role, "kind": kind, "text": text, "ref": ref,
                                                 "created_at": clock.now()})


def to_api(m: dict) -> dict:
    return {"id": m["_id"], "role": m["role"], "kind": m["kind"], "text": m["text"], "ref": m.get("ref"),
            "created_at": clock.iso(m["created_at"])}
