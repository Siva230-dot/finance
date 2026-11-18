from datetime import date
from decimal import Decimal

from app.services.money import add_months, month_start
from tests.conftest import add_tx, categories


def test_budget_crud_and_utilization(client, auth):
    cats = categories(client, auth)
    add_tx(client, auth, description="Groceries", amount="3500", date="2026-11-04", category_id=cats["food"])
    add_tx(client, auth, description="Restaurant", amount="1000", date="2026-11-06", category_id=cats["food"])
    b = client.post("/api/v1/budgets", json={"category_id": cats["food"], "month": "2026-11-15", "amount": "4000"}, headers=auth)
    assert b.status_code == 201
    b = b.json()
    assert b["month"] == "2026-11-01" and b["spent"] == "4500.00" and b["status"] == "exceeded" and b["utilization"] == "112.5"
    dup = client.post("/api/v1/budgets", json={"category_id": cats["food"], "month": "2026-11-01", "amount": "100"}, headers=auth)
    assert dup.status_code == 409
    income = client.post("/api/v1/budgets", json={"category_id": cats["income"], "month": "2026-11-01", "amount": "100"}, headers=auth)
    assert income.status_code == 422
    up = client.patch(f"/api/v1/budgets/{b['id']}", json={"amount": "6000"}, headers=auth).json()
    assert up["status"] == "on_track" and up["remaining"] == "1500.00"
    listing = client.get("/api/v1/budgets", params={"month": "2026-11-01"}, headers=auth).json()
    assert listing["totals"]["budgeted"] == "6000.00"
    assert client.delete(f"/api/v1/budgets/{b['id']}", headers=auth).status_code == 204
    # re-create after soft delete is allowed (partial unique index)
    assert client.post("/api/v1/budgets", json={"category_id": cats["food"], "month": "2026-11-01", "amount": "100"}, headers=auth).status_code == 201


def test_recommendations_require_approval(client, auth):
    cats = categories(client, auth)
    this = month_start(date.today())
    for i, amt in zip(range(3, 0, -1), ["5000", "5200", "4800"]):
        add_tx(client, auth, description="Groceries", amount=amt, date=add_months(this, -i).replace(day=5).isoformat(), category_id=cats["food"])
    recs = client.post("/api/v1/budgets/recommendations/generate", json={"month": this.isoformat()}, headers=auth).json()
    assert len(recs) == 1
    rec = recs[0]
    assert Decimal(rec["proposed_amount"]) > 0
    assert rec["reason"] and rec["expected_effect"] and rec["confidence"] in ("low", "medium", "high")
    assert rec["historical_basis"]["months_with_data"] == 3
    # Nothing saved until approval
    assert client.get("/api/v1/budgets", params={"month": this.isoformat()}, headers=auth).json()["items"] == []
    r = client.post(f"/api/v1/budgets/recommendations/{rec['id']}/decision", json={"approve": True}, headers=auth).json()
    assert r["status"] == "approved"
    items = client.get("/api/v1/budgets", params={"month": this.isoformat()}, headers=auth).json()["items"]
    assert items[0]["amount"] == rec["proposed_amount"]
    again = client.post(f"/api/v1/budgets/recommendations/{rec['id']}/decision", json={"approve": True}, headers=auth)
    assert again.status_code == 409


def test_savings_goal_lifecycle(client, auth):
    target_date = add_months(date.today(), 8).isoformat()
    g = client.post("/api/v1/savings", json={"name": "New laptop", "target_amount": "60000", "current_amount": "20000", "target_date": target_date}, headers=auth)
    assert g.status_code == 201
    g = g.json()
    assert g["remaining_amount"] == "40000.00" and g["progress_percent"] == "33.3"
    assert g["months_remaining"] == 8 and g["required_monthly"] == "5000.00"
    g2 = client.post(f"/api/v1/savings/{g['id']}/contributions", json={"amount": "5000"}, headers=auth).json()
    assert g2["current_amount"] == "25000.00" and len(g2["contributions"]) == 2
    assert client.post(f"/api/v1/savings/{g['id']}/contributions", json={"amount": "-30000"}, headers=auth).status_code == 422
    g3 = client.patch(f"/api/v1/savings/{g['id']}", json={"target_amount": "75000"}, headers=auth).json()
    assert g3["remaining_amount"] == "50000.00"
    done = client.post(f"/api/v1/savings/{g['id']}/contributions", json={"amount": "50000"}, headers=auth).json()
    assert done["status"] == "completed" and done["progress_percent"] == "100.0"
    assert client.delete(f"/api/v1/savings/{g['id']}", headers=auth).status_code == 204
    assert client.get("/api/v1/savings", headers=auth).json() == []
    past = client.post("/api/v1/savings", json={"name": "x", "target_amount": "10", "target_date": "2020-01-01"}, headers=auth)
    assert past.status_code == 422


def test_reports(client, auth):
    add_tx(client, auth, description="Salary", amount="50000", type="income", date=date.today().isoformat())
    add_tx(client, auth, description="Rent", amount="15000", date=date.today().isoformat())
    r = client.get("/api/v1/reports/monthly", headers=auth).json()
    assert r["summary"]["income"] == "50000.00" and r["summary"]["savings"] == "35000.00" and r["summary"]["savings_rate"] == "70.0"
    pdf = client.get("/api/v1/reports/monthly/download", params={"format": "pdf"}, headers=auth)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    csv = client.get("/api/v1/reports/annual/download", params={"format": "csv"}, headers=auth)
    assert csv.status_code == 200 and "Annual Summary" in csv.text
    assert len(client.get("/api/v1/reports", headers=auth).json()) == 2


def test_analytics_overview(client, auth):
    today = date.today()
    add_tx(client, auth, description="Salary", amount="40000.10", type="income", date=today.isoformat())
    add_tx(client, auth, description="Groceries", amount="0.10", date=today.isoformat())
    add_tx(client, auth, description="Groceries", amount="0.20", date=today.isoformat())
    o = client.get("/api/v1/analytics/overview", headers=auth).json()
    assert o["summary"]["expenses"] == "0.30"  # exact decimal arithmetic (0.1 + 0.2)
    assert o["summary"]["savings"] == "39999.80"
    assert o["total_balance"] == "39999.80"
    assert o["category_breakdown"][0]["slug"] == "food"
    assert len(o["monthly_series"]) == 6 and o["insights"]
