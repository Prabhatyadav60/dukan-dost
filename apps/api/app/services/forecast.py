"""Deterministic forecast engine (spec §10). Pure functions: every rupee is computed here, never by a model."""
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

FESTIVALS_PATH = Path(__file__).resolve().parents[2] / "data" / "festivals.json"
DUES_GRACE_DAYS = 3


def load_festivals() -> list[dict]:
    return json.loads(FESTIVALS_PATH.read_text())


def cash_estimate(qr_paise: int, cash_share: float) -> int:
    """Cash for a day with no log: qr × r / (1 − r)."""
    r = min(max(cash_share, 0.0), 0.89)
    return round(qr_paise * r / (1 - r)) if r > 0 else 0


def calibrate_cash_share(purchases_paise: int, digital_paise: int, margin: float) -> float:
    """Monthly calibration: implied cash = purchases ÷ (1 − margin) − digital. Returns the new r."""
    total = purchases_paise / (1 - margin)
    cash = max(0.0, total - digital_paise)
    return round(cash / total, 4) if total > 0 else 0.0


@dataclass
class ForecastInputs:
    today: date
    horizon: int
    daily_totals: dict[date, int]  # past days: QR + cash (logged or estimated)
    festivals: list[dict]
    cash_on_hand_paise: int
    received_paise: int  # ledger payments since cash_on_hand_at
    unpaid_expenses: list[tuple[date | None, int]] = field(default_factory=list)
    collectible_paise: int = 0
    margin: float = 0.10
    spent_paise: int = 0  # bills/expenses paid since cash_on_hand was counted


def compute(inp: ForecastInputs) -> dict:
    # baseline per weekday from the last 28 completed days
    by_wd: dict[int, list[int]] = {}
    for i in range(1, 29):
        d = inp.today - timedelta(days=i)
        if d in inp.daily_totals:
            by_wd.setdefault(d.weekday(), []).append(inp.daily_totals[d])
    overall = [v for vs in by_wd.values() for v in vs]
    fallback = round(sum(overall) / len(overall)) if overall else 0
    baseline = {wd: round(sum(vs) / len(vs)) for wd, vs in by_wd.items()}

    horizon_end = inp.today + timedelta(days=inp.horizon)
    festival = None
    for f in inp.festivals:
        start = date.fromisoformat(f["window"][0])
        if inp.today < start <= horizon_end:
            festival = f
            break
    uplift = {date.fromisoformat(k): v for k, v in (festival or {}).get("uplift", {}).items()}

    daily = []
    for i in range(1, inp.horizon + 1):
        d = inp.today + timedelta(days=i)
        b = baseline.get(d.weekday(), fallback)
        u = uplift.get(d, 1.0)
        daily.append({"date": d, "baseline_paise": b, "uplift": u, "forecast_paise": round(b * u)})

    breakdown = {"cash_on_hand_paise": inp.cash_on_hand_paise, "received_paise": inp.received_paise,
                 "profit_to_buy_paise": 0, "dues_paise": 0, "spent_paise": inp.spent_paise}
    out = {"breakdown": breakdown, "festival": None, "buy_by_date": None, "daily": daily, "stock_needed_paise": 0,
           "cash_available_paise": 0, "gap_paise": 0, "dues_paise": 0, "profit_to_buy_paise": 0,
           "plan": {"collect_paise": 0, "loan_paise": 0},
           "assumptions": {"margin": inp.margin, "dues_grace_days": DUES_GRACE_DAYS}}
    if not festival:
        return out

    w0, w1 = (date.fromisoformat(x) for x in festival["window"])
    buy_by = w0 - timedelta(days=1)
    extra = sum(x["forecast_paise"] - x["baseline_paise"] for x in daily if w0 <= x["date"] <= w1)
    stock_needed = round(extra * (1 - inp.margin))
    profit_to_buy = round(sum(x["forecast_paise"] for x in daily if x["date"] <= buy_by) * inp.margin)
    dues_cutoff = buy_by + timedelta(days=DUES_GRACE_DAYS)
    dues = sum(amt for due, amt in inp.unpaid_expenses if due is not None and due <= dues_cutoff)
    cash_available = inp.cash_on_hand_paise + inp.received_paise + profit_to_buy - dues - inp.spent_paise
    gap = max(0, stock_needed - cash_available)
    collect = min(gap, inp.collectible_paise)
    breakdown.update(profit_to_buy_paise=profit_to_buy, dues_paise=dues)
    out.update({
        "festival": {"name": festival["name"], "date": festival["date"], "window": festival["window"]},
        "buy_by_date": buy_by, "stock_needed_paise": stock_needed, "cash_available_paise": cash_available,
        "gap_paise": gap, "dues_paise": dues, "profit_to_buy_paise": profit_to_buy,
        "plan": {"collect_paise": collect, "loan_paise": gap - collect},
    })
    return out
