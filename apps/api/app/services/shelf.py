"""Shelf scans: first photo → placement tips; later photos → compared with the last 7 days."""
from datetime import timedelta

from .. import clock
from ..ai import get_llm
from ..db import MerchantScopedRepo
from . import media, thread

LOOKBACK_DAYS = 7
MAX_EARLIER = 3  # most recent distinct earlier days sent alongside today's photo


def scan_api(scan: dict) -> dict:
    return {"scan_id": scan["_id"], "first_scan": scan["first_scan"],
            "compared_with_dates": scan["compared_with_dates"], "comparable": scan["comparable"],
            "findings": scan["findings"], "created_at": clock.iso(scan["created_at"])}


async def scan(repo: MerchantScopedRepo, label: str, data: bytes) -> dict:
    mt, ext = media.sniff_image(data)
    key = await media.save_image(repo, "shelf", data, ext, mt)
    today = clock.today_ist()
    lo = clock.ist_midnight_utc(today - timedelta(days=LOOKBACK_DAYS))
    hi = clock.ist_midnight_utc(today)  # earlier days only; a re-take today is not "yesterday"
    prior = await repo.find("shelf_scans", {"shelf_label": label, "created_at": {"$gte": lo, "$lt": hi}},
                            sort=[("created_at", -1)])
    per_day: dict[str, dict] = {}
    for p in prior:  # newest scan of each day
        per_day.setdefault(clock.to_ist_date(p["created_at"]).isoformat(), p)
    days = sorted(per_day)[-MAX_EARLIER:]
    earlier = []
    for d in days:
        img = await media.load_image(repo, per_day[d]["image_key"])
        if img:
            earlier.append((d, img[0], img[1]))

    result = await get_llm().compare_shelf(earlier, (mt, data))
    first = not earlier
    findings = [f.model_dump() for f in result.findings
                if f.section.strip() and "organis" not in f.note.lower() and not (first and f.status == "restock")][:5]
    doc = await repo.insert("shelf_scans", {
        "shelf_label": label, "image_key": key, "first_scan": first,
        "compared_with": [per_day[d]["_id"] for d, _, _ in earlier],
        "compared_with_dates": [d for d, _, _ in earlier], "comparable": bool(result.comparable and earlier),
        "findings": findings, "created_at": clock.now()})

    await thread.add(repo, "merchant", "photo", "Shelf photo")
    restock = [f["section"] for f in findings if f["status"] == "restock"]
    tips = [f["note"] for f in findings if f["status"] == "tip"]
    if first:
        text = "Pehli shelf photo save kar li. Kal phir photo lein, main pichhle 7 din se compare karunga."
    else:
        text = f"Pichhle {len(earlier)} din ki photos se compare kiya. "
        text += f"Restock karein: {', '.join(restock)}." if restock else "Koi section khaali nahi lag raha."
    if tips:
        text += " Tip: " + " ".join(tips[:2])
    await thread.add(repo, "assistant", "text", text, {"type": "shelf_scan", "id": doc["_id"]})
    return scan_api(doc)


async def latest(repo: MerchantScopedRepo, label: str) -> dict | None:
    s = await repo.find_one("shelf_scans", {"shelf_label": label}, sort=[("created_at", -1)])
    return scan_api(s) if s else None
