import json
from datetime import date

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.graph import classify_intent, keyword_intent
from tests.conftest import add_tx, categories, register, tool_call

CHAT = "/api/v1/assistant/chat"


def chat(client, auth, message, conversation_id=None):
    r = client.post(CHAT, json={"message": message, "conversation_id": conversation_id}, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def last_tool_result(messages) -> dict:
    tm = [m for m in messages if isinstance(m, ToolMessage)][-1]
    return json.loads(tm.content)


@pytest.mark.parametrize("text,intent", [
    ("Add ₹500 for groceries today", "transaction"),
    ("Show my last five expenses", "transaction"),
    ("Delete the duplicate transaction from November 5", "transaction"),
    ("Create a monthly food budget of ₹4,000", "budget"),
    ("Which categories have exceeded their budgets?", "budget"),
    ("Create a laptop savings goal of ₹60,000", "savings"),
    ("How much more do I need to save?", "savings"),
    ("Compare this month with last month", "analysis"),
    ("Generate my monthly financial report", "analysis"),
    ("Recategorize my Uber expenses", "categorization"),
])
def test_keyword_intent(text, intent):
    assert keyword_intent(text)[0] == intent


def test_llm_intent_fallback():
    class Fake:
        def invoke(self, _):
            return AIMessage(content='{"intent": "savings"}')

    assert classify_intent("hello there, what's up", Fake()) == ("savings", "llm")
    assert classify_intent("hello there", None) == ("general", "default")


def test_create_transaction_requires_confirmation_then_executes(client, auth, fake_llm):
    fake = fake_llm(
        tool_call("create_transaction", {"description": "Groceries", "amount": 500, "type": "expense", "category": "groceries", "date": "today"}),
        AIMessage(content="I've prepared a ₹500 grocery expense for today. Should I add it?"),
    )
    r = chat(client, auth, "Add ₹500 for groceries today")
    msg = r["message"]
    assert "Should I add it" in msg["content"]
    assert msg["meta"]["intent"] == "transaction" and msg["meta"]["requires_confirmation"]
    card = msg["meta"]["cards"][0]
    assert card["type"] == "confirmation" and card["summary"]["fields"]["Category"] == "Food and Groceries"
    assert msg["meta"]["tool_events"][0] == {"tool": "create_transaction", "status": "confirmation_required", "args": msg["meta"]["tool_events"][0]["args"]}
    # Not written yet
    assert client.get("/api/v1/transactions", headers=auth).json()["total"] == 0
    # User says yes -> deterministic execution, no LLM call
    calls_before = len(fake.calls)
    done = chat(client, auth, "Yes", r["conversation_id"])["message"]
    assert len(fake.calls) == calls_before
    assert done["content"].startswith("Done.") and "500.00" in done["content"]
    txs = client.get("/api/v1/transactions", headers=auth).json()
    assert txs["total"] == 1 and txs["items"][0]["amount"] == "500.00" and txs["items"][0]["transaction_date"] == date.today().isoformat()


def test_model_cannot_claim_success_before_confirmation(client, auth, fake_llm):
    fake_llm(
        tool_call("create_transaction", {"description": "Coffee", "amount": "120", "type": "expense"}),
        AIMessage(content="Done! Your coffee has been added successfully."),
    )
    msg = chat(client, auth, "Add 120 for coffee")["message"]
    assert "nothing has been changed yet" in msg["content"]


def test_update_transaction_flow(client, auth, fake_llm):
    tx = add_tx(client, auth, description="Restaurant dinner", amount="650", date=date.today().isoformat())

    def respond_with_found_id(messages):
        found = last_tool_result(messages)["transactions"][0]["id"]
        return tool_call("update_transaction", {"transaction_id": found, "amount": "750"})

    fake_llm(
        tool_call("list_transactions", {"search": "restaurant"}),
        respond_with_found_id,
        AIMessage(content="I'll change your restaurant expense from ₹650 to ₹750. Confirm?"),
    )
    r = chat(client, auth, "Update my restaurant expense from ₹650 to ₹750")
    events = r["message"]["meta"]["tool_events"]
    assert [e["tool"] for e in events] == ["list_transactions", "update_transaction"]
    card = [c for c in r["message"]["meta"]["cards"] if c["type"] == "confirmation"][0]
    assert client.get(f"/api/v1/transactions/{tx['id']}", headers=auth).json()["amount"] == "650.00"
    res = client.post(f"/api/v1/assistant/confirmations/{card['confirmation_id']}/confirm", headers=auth)
    assert res.status_code == 200 and "Done." in res.json()["message"]["content"]
    assert client.get(f"/api/v1/transactions/{tx['id']}", headers=auth).json()["amount"] == "750.00"
    # double confirm is rejected
    assert client.post(f"/api/v1/assistant/confirmations/{card['confirmation_id']}/confirm", headers=auth).status_code == 409


def test_delete_requires_confirmation_and_can_be_cancelled(client, auth, fake_llm):
    tx = add_tx(client, auth, description="Duplicate taxi", amount="300", date="2026-11-05")
    fake_llm(tool_call("delete_transaction", {"transaction_id": tx["id"]}), AIMessage(content="Delete this ₹300 taxi expense from Nov 5?"))
    r = chat(client, auth, "Delete the duplicate transaction from November 5")
    card = r["message"]["meta"]["cards"][0]
    assert card["action"] == "delete_transaction" and card["summary"]["record"]["id"] == tx["id"]
    cancel = chat(client, auth, "No, cancel", r["conversation_id"])["message"]
    assert "cancelled" in cancel["content"].lower()
    assert client.get(f"/api/v1/transactions/{tx['id']}", headers=auth).status_code == 200
    # confirming a cancelled action is impossible
    assert client.post(f"/api/v1/assistant/confirmations/{card['confirmation_id']}/confirm", headers=auth).status_code == 409


def test_agent_cannot_reach_other_users_records(client, auth, fake_llm):
    other_headers, other_user, _ = register(client, name="Victim")
    victim_tx = add_tx(client, other_headers, description="Victim rent", amount="9999")
    fake = fake_llm(
        tool_call("delete_transaction", {"transaction_id": victim_tx["id"], "user_id": other_user["id"]}),
        lambda msgs: AIMessage(content="I couldn't find that transaction."),
    )
    r = chat(client, auth, "Delete transaction " + victim_tx["id"])
    ev = r["message"]["meta"]["tool_events"][0]
    assert ev["status"] == "error" and "user_id" not in ev["args"]
    assert "not found" in last_tool_result(fake.calls[-1])["error"].lower()
    assert r["message"]["meta"]["cards"] == []
    assert client.get(f"/api/v1/transactions/{victim_tx['id']}", headers=other_headers).status_code == 200


def test_tools_restricted_to_agent_toolset(client, auth, fake_llm):
    tx = add_tx(client, auth)
    # Savings agent tries to call a transaction deletion tool -> rejected.
    fake_llm(tool_call("delete_transaction", {"transaction_id": tx["id"]}), AIMessage(content="Sorry."))
    r = chat(client, auth, "Show all my savings goals")
    assert r["message"]["meta"]["intent"] == "savings"
    assert r["message"]["meta"]["tool_events"][0]["status"] == "rejected"
    assert r["message"]["meta"]["cards"] == []


def test_financial_summary_accuracy(client, auth, fake_llm):
    today = date.today().isoformat()
    cats = categories(client, auth)
    add_tx(client, auth, description="Salary", amount="45000", type="income", date=today)
    add_tx(client, auth, description="Metro card", amount="1200.25", date=today, category_id=cats["transportation"])
    add_tx(client, auth, description="Uber", amount="799.75", date=today, category_id=cats["transportation"])
    add_tx(client, auth, description="Groceries", amount="3000", date=today)
    fake = fake_llm(tool_call("get_financial_summary", {"month": "this month", "category": "Transportation"}),
                    AIMessage(content="You spent ₹2,000 on transportation this month."))
    r = chat(client, auth, "How much did I spend on transportation?")
    result = last_tool_result(fake.calls[-1])
    assert result["income"] == "45000.00" and result["expenses"] == "5000.00" and result["savings"] == "40000.00"
    assert result["expense_by_category"][0]["amount"] == "2000.00"
    assert r["message"]["meta"]["cards"][0]["type"] == "summary"


def test_budget_recommendation_tool(client, auth, fake_llm):
    from app.services.money import add_months, month_start

    cats = categories(client, auth)
    m = month_start(date.today())
    for i in (3, 2, 1):
        add_tx(client, auth, description="Shopping", amount="4000", date=add_months(m, -i).replace(day=3).isoformat(), category_id=cats["shopping"])
    fake = fake_llm(tool_call("calculate_budget_recommendation", {"month": m.isoformat()[:7]}),
                    AIMessage(content="I recommend a shopping budget based on your last three months."))
    r = chat(client, auth, "Recommend a budget for this month")
    result = last_tool_result(fake.calls[-1])
    rec = result["recommendations"][0]
    assert rec["category"] == "Shopping" and rec["basis"]["months_with_data"] == 3
    assert r["message"]["meta"]["cards"][0]["type"] == "recommendations"
    # Recommendation alone never creates a budget
    assert client.get("/api/v1/budgets", headers=auth).json()["items"] == []


def test_savings_goal_via_assistant(client, auth, fake_llm):
    fake_llm(tool_call("create_savings_goal", {"name": "Laptop", "target_amount": "₹60,000"}), AIMessage(content="Create this goal?"))
    r = chat(client, auth, "Create a laptop savings goal of ₹60,000")
    assert r["message"]["meta"]["cards"][0]["summary"]["fields"]["Target"] == "INR 60000.00"
    chat(client, auth, "yes", r["conversation_id"])
    goals = client.get("/api/v1/savings", headers=auth).json()
    assert goals[0]["name"] == "Laptop" and goals[0]["target_amount"] == "60000.00"


def test_groq_failure_is_handled(client, auth, fake_llm):
    class RateLimitError(Exception):
        pass

    fake_llm(raise_exc=RateLimitError("429"))
    r = chat(client, auth, "Analyze my spending this month")
    assert "rate limit" in r["message"]["content"].lower()
    assert r["message"]["meta"]["error"] == "rate_limited"


def test_iteration_limit(client, auth, fake_llm):
    fake_llm(*[tool_call("list_transactions", {}) for _ in range(20)])
    r = chat(client, auth, "Show all my transactions this month")
    assert len(r["message"]["meta"]["tool_events"]) == 5  # AGENT_MAX_ITERATIONS


def test_llm_not_configured(client, auth):
    r = chat(client, auth, "Hello")
    assert r["message"]["meta"]["error"] == "llm_not_configured"


def test_history_is_per_user(client, auth, other_auth, fake_llm):
    fake_llm(AIMessage(content="Hello!"), intent="general")
    r = chat(client, auth, "Hi JOCASTA")
    assert len(client.get(f"/api/v1/assistant/conversations/{r['conversation_id']}/messages", headers=auth).json()) == 2
    assert client.get(f"/api/v1/assistant/conversations/{r['conversation_id']}/messages", headers=other_auth).status_code == 404
    assert client.get("/api/v1/assistant/conversations", headers=other_auth).json() == []
    bad = client.post(CHAT, json={"message": "hi", "conversation_id": r["conversation_id"]}, headers=other_auth)
    assert bad.status_code == 404
