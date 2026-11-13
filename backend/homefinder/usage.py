from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder.config import get_settings
from homefinder.db import session_scope
from homefinder.models import ApiUsage

RIYADH = ZoneInfo("Asia/Riyadh")


class BudgetExceeded(Exception):
    pass


def month_key(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(RIYADH).strftime("%Y-%m")


def day_key(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(RIYADH).strftime("%Y-%m-%d")


def _row(s: Session, provider: str, period: str) -> ApiUsage:
    row = s.scalar(select(ApiUsage).where(ApiUsage.provider == provider, ApiUsage.period == period).with_for_update())
    if row is None:
        row = ApiUsage(provider=provider, period=period, cost_usd=0.0, calls=0)
        s.add(row)
    return row


def spend(provider: str, cost_usd: float) -> None:
    """Charge an OpenAI call against OPENAI_MONTHLY_CAP_USD (checked before the call, so one call may overshoot)."""
    cap = get_settings().openai_monthly_cap_usd
    with session_scope() as s:
        row = _row(s, provider, month_key())
        if row.cost_usd >= cap:
            raise BudgetExceeded(f"{provider} monthly cap {cap} USD reached")
        row.cost_usd += cost_usd
        row.calls += 1


def use_requests(provider: str, n: int, reserve: float = 0.0) -> None:
    """Count `n` TomTom requests before they are sent. Raises BudgetExceeded (and counts nothing) when they would
    go over TOMTOM_DAILY_REQUEST_CAP or TOMTOM_MONTHLY_REQUEST_CAP. `reserve` (0..1) keeps that share of both caps
    free for callers that pass 0, e.g. bulk enrichment passes 0.2 so trip routing still works late in the day."""
    st = get_settings()
    caps = {day_key(): st.tomtom_daily_request_cap, month_key(): st.tomtom_monthly_request_cap}
    with session_scope() as s:
        rows = [(_row(s, provider, period), cap) for period, cap in caps.items()]
        for row, cap in rows:
            if row.calls + n > cap * (1 - reserve):
                raise BudgetExceeded(f"{provider} request cap reached ({row.calls} of {cap} for {row.period})")
        for row, _ in rows:
            row.calls += n
