"""Exercise every JOCASTA tool directly through ToolContext, then execute the resulting confirmations."""
import uuid
from datetime import date

import pytest

from app.agents import actions
from app.agents.tools import ToolContext, build_tools, parse_month, parse_when
from app.core.errors import AppError
from app.models import User
from tests.conftest import add_tx, categories, register


@pytest.fixture
def ctx(client, db):
    headers, user, _ = register(client)
    u = db.get(User, uuid.UUID(user["id"]))
    return ToolContext(db=db, user=u), headers


def run(ctx, tools, tool_name, **args):
    out = tools[tool_name].invoke(args)
    if isinstance(out, dict) and out.get("status") == "confirmation_required":
        _, result = actions.confirm(ctx.db, ctx.user, uuid.UUID(out["confirmation_id"]))
        return out, result
    return out, None


def test_all_tool_names_present(ctx):
    expected = {"create_transaction", "list_transactions", "get_transaction", "update_transaction", "delete_transaction", "create_budget",
                "list_budgets", "update_budget", "delete_budget", "create_savings_goal", "list_savings_goals", "update_savings_goal",
                "delete_savings_goal", "record_savings_contribution", "get_financial_summary", "analyze_spending",
                "calculate_budget_recommendation", "generate_financial_report"}
    assert expected <= set(build_tools(ctx[0]))
    for t in build_tools(ctx[0]).values():
        assert "user_id" not in t.args  # identity is never a tool argument


def test_budget_tools(ctx, client):
    c, headers = ctx
    tools = build_tools(c)
    cats = categories(client, headers)
    add_tx(client, headers, description="Clothes", amount="3500", date=date.today().isoformat(), category_id=cats["shopping"])
    _, res = run(c, tools, "create_budget", category="Shopping", amount="3000")
    assert res["operation"] == "created"
    out, _ = run(c, tools, "create_budget", category="Shopping", amount="3000")
    assert out["status"] == "exists"
    exceeded, _ = run(c, tools, "list_budgets", only_exceeded=True)
    assert exceeded["budgets"][0]["category"]["name"] == "Shopping"
    _, res = run(c, tools, "update_budget", category="shopping", amount=5000)
    assert res["record"]["amount"] == "5000.00"
    _, res = run(c, tools, "delete_budget", category="Shopping")
    assert res["operation"] == "deleted"
    with pytest.raises(AppError):
        tools["delete_budget"].invoke({"category": "Shopping"})


def test_savings_tools(ctx):
    c, _ = ctx
    tools = build_tools(c)
    _, res = run(c, tools, "create_savings_goal", name="Old travel fund", target_amount="20000")
    _, res = run(c, tools, "create_savings_goal", name="Laptop", target_amount="60000", current_amount="20000")
    _, res = run(c, tools, "record_savings_contribution", goal_name="laptop", amount="5000")
    assert res["record"]["current_amount"] == "25000.00"
    _, res = run(c, tools, "update_savings_goal", goal_name="Laptop", target_amount="75000")
    assert res["record"]["remaining_amount"] == "50000.00"
    listing, _ = run(c, tools, "list_savings_goals")
    assert listing["total_remaining_active"] == "70000.00"
    _, res = run(c, tools, "delete_savings_goal", goal_name="old travel")
    assert res["operation"] == "deleted"
    with pytest.raises(AppError):
        tools["update_savings_goal"].invoke({"goal_name": "nonexistent", "target_amount": "1"})


def test_transaction_and_analysis_tools(ctx, client):
    c, headers = ctx
    tools = build_tools(c)
    _, res = run(c, tools, "create_transaction", description="Salary", amount="50000", type="income", date="today")
    _, res = run(c, tools, "create_transaction", description="Zomato", amount="450", type="expense")
    assert res["record"]["category"] == "Food and Groceries"
    tx_id = res["record"]["id"]
    got, _ = run(c, tools, "get_transaction", transaction_id=tx_id)
    assert got["amount"] == "450.00"
    _, res = run(c, tools, "delete_transaction", transaction_id=tx_id)
    assert res["operation"] == "deleted"
    analysis, _ = run(c, tools, "analyze_spending", month="this month")
    assert analysis["summary"]["income"] == "50000.00" and "month_over_month" in analysis
    report, _ = run(c, tools, "generate_financial_report", report_type="monthly")
    assert report["summary"]["savings"] == "50000.00"
    annual, _ = run(c, tools, "generate_financial_report", report_type="annual", period=str(date.today().year))
    assert len(annual["months"]) == 12
    sug, _ = run(c, tools, "suggest_category", description="Uber ride")
    assert sug["category"] == "Transportation"
    with pytest.raises(Exception):
        tools["create_transaction"].invoke({"description": "x", "amount": "-5", "type": "expense"})
    with pytest.raises(AppError):
        tools["create_transaction"].invoke({"description": "x", "amount": "5", "type": "expense", "category": "Nonexistent category zz"})


def test_date_parsing():
    assert parse_when("today") == date.today()
    assert parse_when("2026-11-05") == date(2026, 11, 5)
    assert parse_month("2026-03") == date(2026, 3, 1)
    with pytest.raises(AppError):
        parse_when("someday")


def test_expired_confirmation(ctx):
    from datetime import datetime, timedelta, timezone

    c, _ = ctx
    tools = build_tools(c)
    out = tools["create_savings_goal"].invoke({"name": "Bike", "target_amount": "1000"})
    pc = actions.get_pending(c.db, c.user.id, uuid.UUID(out["confirmation_id"]))
    pc.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    c.db.commit()
    with pytest.raises(AppError) as e:
        actions.confirm(c.db, c.user, pc.id)
    assert e.value.status_code == 410
