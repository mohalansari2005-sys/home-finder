from pathlib import Path

import yaml

EVALS = Path(__file__).parent / "evals.yaml"
TOOLS = {"get_preferences", "update_preferences", "search_listings", "get_listing", "compare_listings", "request_scrape"}


def test_evals_file_is_well_formed():
    cases = yaml.safe_load(EVALS.read_text("utf-8"))
    assert len(cases) == 15 and len({c["name"] for c in cases}) == 15
    for c in cases:
        assert c["messages"] and set(c["expect_tools"]) <= TOOLS, c["name"]
        assert set(c) <= {"name", "messages", "expect_tools", "expect_prefs", "expect_prefs_cmp", "expect_prefs_contains"}
