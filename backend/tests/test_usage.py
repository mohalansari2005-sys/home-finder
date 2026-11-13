from datetime import datetime, UTC

import pytest

from homefinder import usage
from homefinder.models import ApiUsage


def test_month_and_day_keys_use_riyadh_time():
    assert usage.month_key(datetime(2026, 11, 30, 22, 0, tzinfo=UTC)) == "2026-12"
    assert usage.day_key(datetime(2026, 11, 30, 22, 0, tzinfo=UTC)) == "2026-12-01"


def test_spend_until_cap(db, settings_env):
    settings_env(OPENAI_MONTHLY_CAP_USD="0.02")
    usage.spend("openai", 0.01)
    usage.spend("openai", 0.01)
    with pytest.raises(usage.BudgetExceeded):
        usage.spend("openai", 0.01)
    usage.use_requests("tomtom", 1)  # separate provider unaffected


def test_requests_stop_at_the_daily_cap_and_count_nothing_when_refused(db, settings_env):
    settings_env(TOMTOM_DAILY_REQUEST_CAP="5", TOMTOM_MONTHLY_REQUEST_CAP="100")
    usage.use_requests("tomtom", 3)
    with pytest.raises(usage.BudgetExceeded):
        usage.use_requests("tomtom", 3)  # 6 > 5: a batch is all or nothing
    usage.use_requests("tomtom", 2)
    with pytest.raises(usage.BudgetExceeded):
        usage.use_requests("tomtom", 1)
    rows = {r.period: r.calls for r in db.query(ApiUsage).filter_by(provider="tomtom")}
    assert rows == {usage.day_key(): 5, usage.month_key(): 5}


def test_requests_stop_at_the_monthly_cap(db, settings_env):
    settings_env(TOMTOM_DAILY_REQUEST_CAP="100", TOMTOM_MONTHLY_REQUEST_CAP="10")
    db.add(ApiUsage(provider="tomtom", period=usage.month_key(), cost_usd=0.0, calls=9))  # earlier days this month
    db.commit()
    usage.use_requests("tomtom", 1)
    with pytest.raises(usage.BudgetExceeded):
        usage.use_requests("tomtom", 1)


def test_reserve_keeps_a_share_of_the_caps_for_other_callers(db, settings_env):
    settings_env(TOMTOM_DAILY_REQUEST_CAP="10", TOMTOM_MONTHLY_REQUEST_CAP="1000")
    usage.use_requests("tomtom", 8, reserve=0.2)
    with pytest.raises(usage.BudgetExceeded):
        usage.use_requests("tomtom", 1, reserve=0.2)  # bulk enrichment stops at 80%
    usage.use_requests("tomtom", 2)  # trip planning (no reserve) may use the rest
