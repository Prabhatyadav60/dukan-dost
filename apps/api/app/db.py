"""Mongo client plus MerchantScopedRepo: route code never touches collections without merchant_id."""
from typing import Any

from bson import ObjectId

from .config import get_settings

_client: Any = None


def new_id() -> str:
    return str(ObjectId())


def get_db():
    global _client
    s = get_settings()
    if _client is None:
        if s.mongo_uri == "memory":
            from mongomock_motor import AsyncMongoMockClient
            _client = AsyncMongoMockClient()
        else:
            from motor.motor_asyncio import AsyncIOMotorClient
            _client = AsyncIOMotorClient(s.mongo_uri, tz_aware=False)
    return _client[s.mongo_db]


def reset_client() -> None:
    global _client
    _client = None


async def create_indexes(db) -> None:
    await db.merchants.create_index("phone", unique=True)
    await db.customers.create_index([("merchant_id", 1), ("name_key", 1)], unique=True)
    await db.ledger_entries.create_index([("merchant_id", 1), ("customer_id", 1), ("created_at", 1)])
    await db.expenses.create_index([("merchant_id", 1), ("status", 1), ("due_date", 1)])
    await db.transactions.create_index([("merchant_id", 1), ("ts", 1)])
    await db.cash_logs.create_index([("merchant_id", 1), ("date", 1)], unique=True)
    await db.payment_links.create_index([("merchant_id", 1), ("customer_id", 1), ("status", 1)])
    await db.reminders.create_index([("merchant_id", 1), ("customer_id", 1), ("created_at", 1)])
    await db.forecasts.create_index([("merchant_id", 1), ("generated_at", -1)])
    await db.events.create_index([("merchant_id", 1), ("type", 1), ("ts", 1)])
    await db.thread_messages.create_index([("merchant_id", 1), ("created_at", 1)])
    await db.shelf_scans.create_index([("merchant_id", 1), ("shelf_label", 1), ("created_at", 1)])


class MerchantScopedRepo:
    def __init__(self, db, merchant_id: str):
        self.db = db
        self.merchant_id = merchant_id

    def _f(self, filt: dict | None) -> dict:
        return {**(filt or {}), "merchant_id": self.merchant_id}

    async def find(self, col: str, filt: dict | None = None, sort: list | None = None, limit: int = 0) -> list[dict]:
        cur = self.db[col].find(self._f(filt))
        if sort:
            cur = cur.sort(sort)
        if limit:
            cur = cur.limit(limit)
        return [d async for d in cur]

    async def find_one(self, col: str, filt: dict | None = None, sort: list | None = None) -> dict | None:
        docs = await self.find(col, filt, sort, limit=1)
        return docs[0] if docs else None

    async def get(self, col: str, _id: str) -> dict | None:
        return await self.db[col].find_one(self._f({"_id": _id}))

    async def insert(self, col: str, doc: dict) -> dict:
        doc = {"_id": doc.get("_id") or new_id(), **doc, "merchant_id": self.merchant_id}
        await self.db[col].insert_one(doc)
        return doc

    async def update(self, col: str, filt: dict, update: dict, upsert: bool = False) -> None:
        await self.db[col].update_one(self._f(filt), update, upsert=upsert)

    async def update_many(self, col: str, filt: dict, update: dict) -> None:
        await self.db[col].update_many(self._f(filt), update)
