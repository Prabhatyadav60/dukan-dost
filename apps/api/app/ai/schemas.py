from typing import Literal

from pydantic import BaseModel, Field


class EntryDraft(BaseModel):
    intent: Literal["credit", "payment", "expense", "cash_sale"]
    customer_name: str | None = None
    amount_paise: int = Field(gt=0)
    items: list[str] = []
    vendor: str | None = None
    category: Literal["stock", "rent", "staff", "other"] | None = None
    confidence: float = Field(ge=0, le=1)


class BillLine(BaseModel):
    name: str
    qty: float | None = None
    unit: str | None = None
    amount_paise: int


class BillDraft(BaseModel):
    vendor: str | None = None
    bill_date: str | None = None
    due_date: str | None = None
    line_items: list[BillLine] = []
    total_paise: int | None = None
    unreadable_fields: list[str] = []


class Message(BaseModel):
    message: str


class Explanation(BaseModel):
    text: str


class ShelfFinding(BaseModel):
    section: str
    status: Literal["restock", "tip"]
    note: str


class ShelfResult(BaseModel):
    comparable: bool
    findings: list[ShelfFinding] = []
