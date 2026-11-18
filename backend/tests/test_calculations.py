from datetime import date
from decimal import Decimal

import pytest

from app.services.budgets import compute_recommendation
from app.services.categories import categorize_many, rule_categorize
from app.services.money import add_months, pct, to_money
from app.services.savings import goal_progress, months_between


def test_money_helpers():
    assert to_money("0.1") + to_money("0.2") == Decimal("0.30")
    assert to_money(0.1) == Decimal("0.10")
    assert to_money("2.005") == Decimal("2.01")
    with pytest.raises(ValueError):
        to_money("abc")
    assert pct(Decimal("1"), Decimal("3")) == Decimal("33.3")
    assert pct(Decimal("1"), Decimal("0")) == Decimal("0.00")
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_goal_progress_laptop_example():
    p = goal_progress(Decimal("60000"), Decimal("20000"), date(2027, 7, 18), today=date(2026, 11, 18))
    assert p["remaining_amount"] == Decimal("40000.00")
    assert p["months_remaining"] == 8
    assert p["required_monthly"] == Decimal("5000.00")
    assert p["progress_percent"] == Decimal("33.3")
    p = goal_progress(Decimal("1000"), Decimal("0"), date(2027, 2, 1), today=date(2026, 11, 18))
    assert p["months_remaining"] == 3 and p["required_monthly"] == Decimal("333.34")  # rounds up
    assert goal_progress(Decimal("10"), Decimal("15"), None)["remaining_amount"] == 0
    assert months_between(date(2026, 11, 18), date(2026, 11, 20)) == 1


def test_recommendation_is_deterministic_and_explained():
    series = [("2026-05-01", Decimal("0")), ("2026-06-01", Decimal("0")), ("2026-07-01", Decimal("0")),
              ("2026-08-01", Decimal("5000")), ("2026-09-01", Decimal("5000")), ("2026-10-01", Decimal("5000"))]
    a = compute_recommendation("Food and Groceries", "food", series, None)
    b = compute_recommendation("Food and Groceries", "food", series, None)
    assert a["proposed_amount"] == b["proposed_amount"]
    assert a["proposed_amount"] % 50 == 0
    assert a["basis"]["months_with_data"] == 3
    assert a["confidence"] in ("low", "medium") and a["reason"] and a["expected_effect"]
    housing = compute_recommendation("Housing", "housing", [(m, Decimal("15000")) for m, _ in series], Decimal("15000"))
    assert housing["proposed_amount"] == Decimal("15000.00") and housing["confidence"] == "high"


def test_rule_categorization():
    assert rule_categorize("UPI-SWIGGY ORDER 123").slug == "food"
    assert rule_categorize("Uber trip").slug == "transportation"
    assert rule_categorize("NETFLIX.COM").slug == "subscriptions"
    assert rule_categorize("Salary credit ACME").slug == "income"
    assert rule_categorize("Salary credit", "expense") is None or rule_categorize("Salary credit", "expense").slug != "income"
    assert rule_categorize("zzzz unknown") is None
    out = categorize_many(["zzzz unknown", "Uber"], ["expense", "expense"], llm=None)
    assert out[0].slug == "other" and out[0].source == "default" and out[1].source == "rule"
