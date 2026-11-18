from decimal import Decimal

from tests.conftest import add_tx, categories

API = "/api/v1/transactions"


def test_crud_and_auto_categorization(client, auth):
    tx = add_tx(client, auth, description="Swiggy dinner", amount="650.00")
    assert tx["category"]["slug"] == "food"
    assert tx["categorization_source"] == "rule"
    assert Decimal(tx["amount"]) == Decimal("650.00")

    r = client.patch(f"{API}/{tx['id']}", json={"amount": "750.50"}, headers=auth)
    assert r.status_code == 200 and r.json()["amount"] == "750.50"

    cats = categories(client, auth)
    r = client.patch(f"{API}/{tx['id']}", json={"category_id": cats["entertainment"]}, headers=auth)
    assert r.json()["category"]["slug"] == "entertainment" and r.json()["categorization_source"] == "user"

    assert client.delete(f"{API}/{tx['id']}", headers=auth).status_code == 204
    assert client.get(f"{API}/{tx['id']}", headers=auth).status_code == 404
    assert client.get(API, headers=auth).json()["total"] == 0


def test_soft_delete_keeps_audit_row(client, auth, db):
    from app.models import AuditLog, Transaction

    tx = add_tx(client, auth)
    client.delete(f"{API}/{tx['id']}", headers=auth)
    row = db.get(Transaction, __import__("uuid").UUID(tx["id"]))
    assert row is not None and row.deleted_at is not None
    assert db.query(AuditLog).filter(AuditLog.action == "transaction.delete").count() == 1


def test_validation(client, auth):
    bad = [
        {"description": "x", "amount": "-5", "type": "expense", "transaction_date": "2026-11-01"},
        {"description": "x", "amount": "0", "type": "expense", "transaction_date": "2026-11-01"},
        {"description": "x", "amount": "5", "type": "transfer", "transaction_date": "2026-11-01"},
        {"description": "", "amount": "5", "type": "expense", "transaction_date": "2026-11-01"},
        {"description": "x", "amount": "5.123", "type": "expense", "transaction_date": "2026-11-01"},
        {"description": "x", "amount": "5", "type": "expense", "transaction_date": "not-a-date"},
    ]
    for body in bad:
        assert client.post(API, json=body, headers=auth).status_code == 422, body


def test_filters_search_sort(client, auth):
    add_tx(client, auth, description="Salary November", amount="50000", type="income", date="2026-11-01")
    add_tx(client, auth, description="Uber to office", amount="250", date="2026-11-03")
    add_tx(client, auth, description="Amazon headphones", amount="2999", date="2026-11-10")
    add_tx(client, auth, description="Old groceries", amount="400", date="2026-10-15")

    r = client.get(API, params={"type": "expense", "start_date": "2026-11-01", "end_date": "2026-11-30", "sort": "amount", "order": "desc"}, headers=auth).json()
    assert [t["description"] for t in r["items"]] == ["Amazon headphones", "Uber to office"]
    assert client.get(API, params={"search": "uber"}, headers=auth).json()["total"] == 1
    assert client.get(API, params={"search": "transportation"}, headers=auth).json()["total"] == 1  # category name search
    cats = categories(client, auth)
    assert client.get(API, params={"category_id": cats["shopping"]}, headers=auth).json()["total"] == 1
    assert client.get(API, params={"type": "income"}, headers=auth).json()["total"] == 1


def test_export_csv(client, auth):
    add_tx(client, auth, description="Coffee", amount="180")
    r = client.get(f"{API}/export", headers=auth)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "Coffee" in r.text and "180.00" in r.text


def test_duplicates_detected(client, auth):
    add_tx(client, auth, description="Netflix subscription", amount="649", date="2026-11-05")
    add_tx(client, auth, description="NETFLIX  subscription!", amount="649.00", date="2026-11-05")
    add_tx(client, auth, description="Netflix subscription", amount="649", date="2026-10-05")
    groups = client.get(f"{API}/duplicates", headers=auth).json()["groups"]
    assert len(groups) == 1 and len(groups[0]) == 2


def test_recurring(client, auth):
    tx = add_tx(client, auth, description="Rent", amount="15000", date="2026-08-01", is_recurring=True, recurrence_interval="monthly")
    assert tx["is_recurring"]
    created = client.post(f"{API}/recurring/run", headers=auth).json()["created"]
    assert created == 3  # Sep, Oct, Nov (today is after Nov 1)
    assert client.post(f"{API}/recurring/run", headers=auth).json()["created"] == 0  # idempotent
    bad = client.post(API, json={"description": "x", "amount": "5", "type": "expense", "transaction_date": "2026-11-01", "is_recurring": True}, headers=auth)
    assert bad.status_code == 422


def test_custom_category(client, auth):
    r = client.post("/api/v1/categories", json={"name": "Pets", "kind": "expense"}, headers=auth)
    assert r.status_code == 201
    tx = add_tx(client, auth, description="Dog food", category_id=r.json()["id"])
    assert tx["category"]["name"] == "Pets"
    assert client.delete(f"/api/v1/categories/{r.json()['id']}", headers=auth).status_code == 409
