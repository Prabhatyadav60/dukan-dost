"""Deterministic fakes: CI, offline demo fallback, and AI_PROVIDER=fake."""
import re
from pathlib import Path

from .schemas import BillDraft, BillLine, EntryDraft, ShelfFinding, ShelfResult

HINDI_NUMBERS = {
    "saade chaar sau": 450, "dedh sau": 150, "dhai sau": 250, "dedh hazaar": 1500, "dhai hazaar": 2500,
    "sau": 100, "hazaar": 1000, "hazar": 1000,
}
EXPENSE_WORDS = {"rent": "rent", "kiraya": "rent", "salary": "staff", "tankhwah": "staff", "bijli": "other"}


def _amount(text: str) -> int | None:
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(k|hazaar|hazar)?\b", text)
    if m:
        v = float(m.group(1).replace(",", ""))
        if m.group(2):
            v *= 1000
        return round(v * 100)
    for phrase, v in HINDI_NUMBERS.items():
        if phrase in text:
            return v * 100
    return None


class FakeSTT:
    async def transcribe(self, wav_path: str, original_name: str) -> str:
        return Path(original_name).stem.replace("_", " ")


class FakeLLM:
    async def parse_entry(self, transcript: str) -> EntryDraft:
        t = transcript.strip()
        low = t.lower()
        amount = _amount(low) or 100
        conf = 0.95 if _amount(low) else 0.5
        if "cash" in low and re.search(r"\b(aaya|aayi|aaj|sale|bikri)\b", low):
            return EntryDraft(intent="cash_sale", amount_paise=amount, confidence=conf)
        for word, cat in EXPENSE_WORDS.items():
            if word in low:
                return EntryDraft(intent="expense", amount_paise=amount, vendor=word.title(), category=cat,
                                  confidence=conf)
        m = re.match(r"(.+?)\s+ko\s+[\d,]+.*dene\s+hai", low)
        if m:
            return EntryDraft(intent="expense", amount_paise=amount, vendor=m.group(1).title(), category="stock",
                              confidence=conf)
        name_m = re.match(r"^\s*([^\d]+?)\s*(?:ne\s+)?(?=\d)", t)
        name = name_m.group(1).strip(" ,") if name_m else None
        if name and name.lower().endswith(" ne"):
            name = name[:-3].strip()
        if re.search(r"\b(diye|de diye|wapas|jama|paid|lautaye)\b", low) and "udhaar" not in low:
            return EntryDraft(intent="payment", customer_name=name, amount_paise=amount,
                              confidence=conf if name else 0.5)
        items: list[str] = []
        im = re.search(r"(?:udhaar|udhar|credit)[,\s]+(.+)$", low)
        if im:
            items = [w.strip().title() for w in re.split(r",|\baur\b|\band\b", im.group(1)) if w.strip()]
        return EntryDraft(intent="credit", customer_name=name, amount_paise=amount, items=items,
                          confidence=conf if name else 0.5)

    async def read_bill(self, images: list[tuple[str, bytes]]) -> BillDraft:
        lines = [("Atta 10kg", 10, "bag", 420000), ("Doodh 1L", 40, "pkt", 272000), ("Tel 1L", 20, "btl", 310000),
                 ("Chini 1kg", 100, "kg", 450000), ("Dal 1kg", 30, "kg", 388000)]
        return BillDraft(vendor="Balaji Traders", bill_date="2026-10-29", due_date="2026-11-05",
                         line_items=[BillLine(name=n, qty=q, unit=u, amount_paise=a) for n, q, u, a in lines],
                         total_paise=1840000)

    async def write_reminder(self, payload: dict) -> str:
        raise NotImplementedError  # caller falls back to the template

    async def write_explanation(self, payload: dict) -> str:
        raise NotImplementedError  # caller falls back to the template

    async def compare_shelf(self, before, after) -> ShelfResult:
        return ShelfResult(comparable=before is not None, findings=[
            ShelfFinding(section="Atta section", status="restock", note="Kal se kaafi khaali hai. Restock karein."),
            ShelfFinding(section="Biscuits", status="restock", note="Front row almost khaali hai."),
            ShelfFinding(section="Cold drinks", status="tip", note="Cold drinks ko eye level par, counter ke paas rakhein."),
        ])
