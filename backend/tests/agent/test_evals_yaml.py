from pathlib import Path

import yaml

EVALS = Path(__file__).parent / "evals.yaml"
TOOLS = {"get_preferences", "update_preferences", "search_listings", "get_listing", "compare_listings", "request_scrape",
         "get_filter_suggestions", "apply_filter_suggestion", "suggest_visit_trip", "create_visit_trip"}


def test_evals_file_is_well_formed():
    cases = yaml.safe_load(EVALS.read_text("utf-8"))
    assert len(cases) == 20 and len({c["name"] for c in cases}) == 20
    for c in cases:
        assert c["messages"] and set(c["expect_tools"]) | set(c.get("forbid_tools", [])) <= TOOLS, c["name"]
        assert set(c) <= {"name", "messages", "expect_tools", "expect_prefs", "expect_prefs_cmp", "expect_prefs_contains",
                          "start_prefs", "forbid_tools"}
