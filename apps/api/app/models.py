from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .ai.schemas import BillLine


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionReq(Strict):
    phone: str
    otp: str


class ConsentReq(Strict):
    data_use: bool
    cash_share_estimate: float = Field(0.30, gt=0, lt=0.9)
    cash_on_hand_paise: int = Field(0, ge=0)


class CustomerCreate(Strict):
    name: str = Field(min_length=1, max_length=60)
    phone_e164: str | None = Field(None, pattern=r"^\+\d{8,15}$")
    aliases: list[str] = []


class CustomerPatch(Strict):
    phone_e164: str | None = Field(None, pattern=r"^\+\d{8,15}$")
    aliases: list[str] | None = None
    do_not_remind: bool | None = None


class LedgerReq(Strict):
    customer_id: str
    type: Literal["credit", "payment"]
    amount_paise: int = Field(gt=0)
    items: list[str] = []
    source: Literal["voice", "text", "manual"] = "manual"
    transcript: str | None = None
    edited: bool = False  # client sets this when the owner changed the AI draft before saving


class ExpenseReq(Strict):
    vendor: str = Field(min_length=1)
    line_items: list[BillLine] = []
    total_paise: int = Field(gt=0)
    due_date: date | None = None
    category: Literal["stock", "rent", "staff", "other"] = "other"
    source: Literal["bill_scan", "voice", "text", "manual"] = "manual"
    image_keys: list[str] = []
    status: Literal["paid", "unpaid"] = "unpaid"


class ExpensePatch(Strict):
    status: Literal["paid"]


class CashLogReq(Strict):
    date: date
    amount_paise: int = Field(ge=0)
    source: Literal["voice", "text", "manual"] = "manual"


class PaymentLinkReq(Strict):
    customer_id: str
    amount_paise: int = Field(gt=0)
