"""All notions of "now" go through here so DEMO_TODAY makes the demo reproducible."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import get_settings

IST = ZoneInfo("Asia/Kolkata")


def now() -> datetime:
    """Current instant as naive UTC (what MongoDB stores)."""
    real = datetime.now(timezone.utc)
    demo = get_settings().demo_today
    if demo:
        ist = real.astimezone(IST)
        shifted = datetime.combine(date.fromisoformat(demo), ist.time(), tzinfo=IST)
        real = shifted.astimezone(timezone.utc)
    return real.replace(tzinfo=None)


def today_ist() -> date:
    return to_ist_date(now())


def to_ist_date(dt: datetime) -> date:
    return dt.replace(tzinfo=timezone.utc).astimezone(IST).date()


def ist_midnight_utc(d: date) -> datetime:
    """Start of an IST calendar day, as naive UTC."""
    return datetime.combine(d, time(0), tzinfo=IST).astimezone(timezone.utc).replace(tzinfo=None)


def ist_day_range(d: date) -> tuple[datetime, datetime]:
    return ist_midnight_utc(d), ist_midnight_utc(d + timedelta(days=1))


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(microsecond=0).isoformat() + "Z"
