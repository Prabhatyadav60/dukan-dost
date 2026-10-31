from .. import clock
from ..db import MerchantScopedRepo


async def log(repo: MerchantScopedRepo, type_: str, ref_id: str | None = None, **props) -> None:
    await repo.insert("events", {"type": type_, "ref_id": ref_id, "props": props, "ts": clock.now()})
