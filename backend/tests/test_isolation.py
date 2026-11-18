from tests.conftest import add_tx, categories


def test_users_cannot_touch_each_others_data(client, auth, other_auth):
    tx = add_tx(client, auth, description="Private expense")
    cats = categories(client, auth)
    budget = client.post("/api/v1/budgets", json={"category_id": cats["food"], "month": "2026-11-01", "amount": "4000"}, headers=auth).json()
    goal = client.post("/api/v1/savings", json={"name": "Laptop", "target_amount": "60000"}, headers=auth).json()
    custom = client.post("/api/v1/categories", json={"name": "Secret"}, headers=auth).json()

    # Other user sees nothing
    assert client.get("/api/v1/transactions", headers=other_auth).json()["total"] == 0
    assert client.get("/api/v1/budgets", params={"month": "2026-11-01"}, headers=other_auth).json()["items"] == []
    assert client.get("/api/v1/savings", headers=other_auth).json() == []
    assert "Secret" not in [c["name"] for c in client.get("/api/v1/categories", headers=other_auth).json()]
    # ...and cannot read, modify or delete by id
    assert client.get(f"/api/v1/transactions/{tx['id']}", headers=other_auth).status_code == 404
    assert client.patch(f"/api/v1/transactions/{tx['id']}", json={"amount": "1"}, headers=other_auth).status_code == 404
    assert client.delete(f"/api/v1/transactions/{tx['id']}", headers=other_auth).status_code == 404
    assert client.patch(f"/api/v1/budgets/{budget['id']}", json={"amount": "1"}, headers=other_auth).status_code == 404
    assert client.delete(f"/api/v1/budgets/{budget['id']}", headers=other_auth).status_code == 404
    assert client.get(f"/api/v1/savings/{goal['id']}", headers=other_auth).status_code == 404
    assert client.post(f"/api/v1/savings/{goal['id']}/contributions", json={"amount": "5"}, headers=other_auth).status_code == 404
    # Cannot use another user's custom category
    r = client.post("/api/v1/transactions", json={"description": "x", "amount": "5", "type": "expense", "transaction_date": "2026-11-01",
                                                  "category_id": custom["id"]}, headers=other_auth)
    assert r.status_code == 404
    # Analytics are per user
    assert client.get("/api/v1/analytics/summary", params={"start_date": "2026-11-01", "end_date": "2026-11-30"}, headers=other_auth).json()["expenses"] == "0.00"
    # Owner still has everything
    assert client.get(f"/api/v1/transactions/{tx['id']}", headers=auth).status_code == 200
