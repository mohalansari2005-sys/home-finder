from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from homefinder.config import get_settings
from homefinder.db import session_scope
from homefinder.models import ApiUsage

RIYADH = ZoneInfo("Asia/Riyadh")
Provider = Literal["openai", "google"]


class BudgetExceeded(Exception):
    pass


def month_key(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(RIYADH).strftime("%Y-%m")


def _cap(provider: Provider) -> float:
    st = get_settings()
    return st.openai_monthly_cap_usd if provider == "openai" else st.google_monthly_cap_usd


def spend(provider: Provider, cost_usd: float) -> None:
    with session_scope() as s:
        row = s.scalar(select(ApiUsage).where(ApiUsage.provider == provider, ApiUsage.month == month_key())
                       .with_for_update())
        if row is None:
            row = ApiUsage(provider=provider, month=month_key(), cost_usd=0.0, calls=0)
            s.add(row)
        if row.cost_usd >= _cap(provider):
            raise BudgetExceeded(f"{provider} monthly cap {_cap(provider)} USD reached")
        row.cost_usd += cost_usd
        row.calls += 1
