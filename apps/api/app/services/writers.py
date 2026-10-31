"""Model-written words with validation and template fallbacks (spec §9). Numbers are passed in, never generated."""
import re

from ..ai import get_llm

BANNED = ("police", "court", "legal", "case", "penalty", "fine", "byaaj", "interest", "loan")


def reminder_template(name: str, shop: str, amount: str, items: list[str]) -> str:
    items_clause = f" ({', '.join(items)})" if items else ""
    return f"Namaste {name}, {shop} se. Aapka {amount} baaki hai{items_clause}. Paytm / UPI se turant pay karein: {{link}} Dhanyavaad!"


def reminder_valid(msg: str, amount: str) -> bool:
    low = msg.lower()
    return (msg.count("{link}") == 1 and len(msg) <= 320 and amount in msg
            and not any(re.search(rf"\b{w}\b", low) for w in BANNED))


async def reminder(name: str, shop: str, amount: str, items: list[str], attempt: int) -> str:
    try:
        msg = await get_llm().write_reminder({"shop_name": shop, "customer_name": name, "amount": amount,
                                              "items": items, "attempt": attempt})
        if reminder_valid(msg, amount):
            return msg
    except Exception:  # noqa: BLE001 — any model failure falls back to the template
        pass
    return reminder_template(name, shop, amount, items)


def explanation_template(v: dict) -> str:
    s = f"Diwali ke liye ~{v['stock_needed']} ka maal lagega. {v['buy_by']} tak {v['gap']} kam padega. "
    s += f"Pehle {v['collect']} pending udhaar collect karein?"
    if v["loan"] != "₹0":
        s += f" Baaki {v['loan']} ke liye Paytm loan offer dekhein?"
    return s


def explanation_valid(text: str, v: dict) -> bool:
    if not all(val in text for key, val in v.items() if not (key == "loan" and val == "₹0")):
        return False
    stripped = text
    for val in v.values():
        stripped = stripped.replace(val, "")
    return not re.search(r"\d", stripped)


async def explanation(v: dict) -> str:
    try:
        text = await get_llm().write_explanation(v)
        if explanation_valid(text, v):
            return text
    except Exception:  # noqa: BLE001
        pass
    return explanation_template(v)


def bills_explanation(v: dict) -> str:
    """Shortfall caused by bills, not festival stock. Every number is passed in, none generated."""
    s = (f"{v['buy_by']} tak {v.get('reason', 'bills')} chukane ke liye {v['gap']} kam padega. "
         f"Pehle {v['collect']} pending udhaar collect karein?")
    if v["loan"] != "₹0":
        s += f" Baaki {v['loan']} ke liye Paytm loan offer dekhein?"
    return s
