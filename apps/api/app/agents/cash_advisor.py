"""Cash advisor graph: load_inputs → compute → choose_plan → explain → persist.
compute and choose_plan are pure; only explain touches the model."""
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .. import clock
from ..config import get_settings
from ..money import format_paise
from ..services import cash, events, forecast, thread, writers


class AdvisorState(TypedDict, total=False):
    repo: Any
    merchant: dict
    horizon: int
    inputs: forecast.ForecastInputs
    result: dict
    explanation: str | None
    forecast_doc: dict


async def load_inputs(state: AdvisorState) -> AdvisorState:
    inputs = await cash.forecast_inputs(state["repo"], state["merchant"], state["horizon"],
                                        get_settings().forecast_margin)
    return {"inputs": inputs}


def compute(state: AdvisorState) -> AdvisorState:
    return {"result": forecast.compute(state["inputs"])}


def choose_plan(state: AdvisorState) -> AdvisorState:
    # Collect udhaar first, borrow only the remainder — already encoded in compute(); kept as its own node
    # so the policy can grow (e.g. defer non-urgent bills) without touching the maths.
    return {}


async def explain(state: AdvisorState) -> AdvisorState:
    r = state["result"]
    if r["gap_paise"] <= 0:
        return {"explanation": None}
    v = {"stock_needed": format_paise(r["stock_needed_paise"]),
         "buy_by": r["buy_by_date"].strftime("%-d %b"),
         "gap": format_paise(r["gap_paise"]),
         "collect": format_paise(r["plan"]["collect_paise"]),
         "loan": format_paise(r["plan"]["loan_paise"])}
    return {"explanation": await writers.explanation(v)}


async def persist(state: AdvisorState) -> AdvisorState:
    repo, r = state["repo"], state["result"]
    prev = await repo.find_one("forecasts", sort=[("generated_at", -1)])
    doc = await repo.insert("forecasts", {
        "generated_at": clock.now(), "horizon_days": state["horizon"],
        "festival": r["festival"], "buy_by_date": r["buy_by_date"].isoformat() if r["buy_by_date"] else None,
        "daily": [{**d, "date": d["date"].isoformat()} for d in r["daily"]],
        "stock_needed_paise": r["stock_needed_paise"], "cash_available_paise": r["cash_available_paise"],
        "gap_paise": r["gap_paise"], "plan": r["plan"], "explanation": state.get("explanation"),
        "assumptions": {**r["assumptions"], "cash_share": state["merchant"].get("cash_share_estimate")}})
    loan = r["plan"]["loan_paise"]
    if loan > 0:
        offer = await repo.find_one("loan_offers", sort=[("created_at", -1)])
        if not offer or offer["amount_paise"] != loan:
            offer = await repo.insert("loan_offers", {"forecast_id": doc["_id"], "amount_paise": loan,
                                                      "reason": "festival_stock_gap", "status": "shown",
                                                      "created_at": clock.now()})
            await events.log(repo, "offer_shown", offer["_id"], amount_paise=loan)
    # one alert per change in the gap, not one per page view
    if r["gap_paise"] > 0 and (not prev or prev.get("gap_paise") != r["gap_paise"]):
        await thread.add(repo, "assistant", "alert", state["explanation"], {"type": "forecast", "id": doc["_id"]})
    return {"forecast_doc": doc}


def _build():
    g = StateGraph(AdvisorState)
    for name, fn in [("load_inputs", load_inputs), ("compute", compute), ("choose_plan", choose_plan),
                     ("explain", explain), ("persist", persist)]:
        g.add_node(name, fn)
    g.set_entry_point("load_inputs")
    g.add_edge("load_inputs", "compute")
    g.add_edge("compute", "choose_plan")
    g.add_edge("choose_plan", "explain")
    g.add_edge("explain", "persist")
    g.add_edge("persist", END)
    return g.compile()


graph = _build()


async def run(repo, merchant: dict, horizon: int) -> dict:
    out = await graph.ainvoke({"repo": repo, "merchant": merchant, "horizon": horizon})
    return out["forecast_doc"]
