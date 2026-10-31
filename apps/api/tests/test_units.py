from datetime import date

from app.ai.fake import FakeLLM
from app.money import format_paise
from app.services import forecast, writers


def test_cash_estimate():
    assert forecast.cash_estimate(875000, 0.30) == 375000


def test_no_festival():
    inp = forecast.ForecastInputs(today=date(2026, 12, 1), horizon=14,
                                  daily_totals={date(2026, 11, 30): 100}, festivals=forecast.load_festivals(),
                                  cash_on_hand_paise=0, received_paise=0)
    r = forecast.compute(inp)
    assert r["gap_paise"] == 0 and r["festival"] is None


def test_format_paise():
    assert format_paise(125000) == "₹1,250"
    assert format_paise(12345678) == "₹1,23,456.78"


def test_reminder_validation():
    assert not writers.reminder_valid("Namaste, ₹100 baaki, warna police {link}", "₹100")
    assert not writers.reminder_valid("Namaste, ₹100 baaki", "₹100")
    assert writers.reminder_valid("Namaste Anil, ₹100 baaki. {link} Dhanyavaad", "₹100")


async def test_voice_fake_intents():
    llm = FakeLLM()
    assert (await llm.parse_entry("Gupta ji ne 500 diye")).model_dump()["intent"] == "payment"
    assert (await llm.parse_entry("Gupta ji ne 500 diye")).customer_name == "Gupta ji"
    assert (await llm.parse_entry("aaj cash 3500 aaya")).intent == "cash_sale"
    assert (await llm.parse_entry("rent 8000 diya")).category == "rent"
