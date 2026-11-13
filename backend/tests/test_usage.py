from datetime import datetime, UTC

import pytest

from homefinder import usage


def test_month_key_uses_riyadh_time():
    assert usage.month_key(datetime(2026, 11, 30, 22, 0, tzinfo=UTC)) == "2026-12"


def test_spend_until_cap(db, settings_env):
    settings_env(GOOGLE_MONTHLY_CAP_USD="0.02")
    usage.spend("google", 0.01)
    usage.spend("google", 0.01)
    with pytest.raises(usage.BudgetExceeded):
        usage.spend("google", 0.01)
    usage.spend("openai", 0.5)  # separate provider unaffected


def test_reserve_keeps_a_share_of_the_cap_for_other_callers(db, settings_env):
    settings_env(GOOGLE_MONTHLY_CAP_USD="1.0")
    usage.spend("google", 0.79, reserve=0.2)
    usage.spend("google", 0.02, reserve=0.2)  # the check is before the call: 0.79 < 0.8 passes, total is now 0.81
    with pytest.raises(usage.BudgetExceeded):
        usage.spend("google", 0.01, reserve=0.2)
    usage.spend("google", 0.1)  # no reserve: allowed until the full cap
