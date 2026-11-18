from tests.conftest import register

API = "/api/v1"


def test_register_and_login(client):
    headers, user, email = register(client)
    assert user["currency"] == "INR"
    r = client.post(f"{API}/auth/login", json={"email": email.upper(), "password": "Secure123pass"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    me = client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == email


def test_password_is_hashed_with_argon2(client, db):
    from app.models import User

    _, user, _ = register(client)
    stored = db.get(User, __import__("uuid").UUID(user["id"]))
    assert stored.password_hash.startswith("$argon2")
    assert "Secure123pass" not in stored.password_hash


def test_login_wrong_password(client):
    _, _, email = register(client)
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "wrongpass1"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_duplicate_email(client):
    _, _, email = register(client)
    r = client.post(f"{API}/auth/register", json={"email": email, "full_name": "X", "password": "Secure123pass"})
    assert r.status_code == 409


def test_weak_password_rejected(client):
    r = client.post(f"{API}/auth/register", json={"email": "weak@example.com", "full_name": "X", "password": "short"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_requires_token(client):
    assert client.get(f"{API}/transactions").status_code == 401
    assert client.get(f"{API}/transactions", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_logout_revokes_token(client, auth):
    assert client.post(f"{API}/auth/logout", headers=auth).status_code == 204
    assert client.get(f"{API}/users/me", headers=auth).status_code == 401


def test_profile_update_and_password_change(client):
    headers, _, email = register(client)
    r = client.patch(f"{API}/users/me", json={"currency": "USD", "full_name": "New Name", "theme_preference": "dark"}, headers=headers)
    assert r.json()["currency"] == "USD" and r.json()["theme_preference"] == "dark"
    assert client.patch(f"{API}/users/me", json={"currency": "XYZ"}, headers=headers).status_code == 422
    bad = client.post(f"{API}/users/me/password", json={"current_password": "nope", "new_password": "Another123"}, headers=headers)
    assert bad.status_code == 400
    ok = client.post(f"{API}/users/me/password", json={"current_password": "Secure123pass", "new_password": "Another123"}, headers=headers)
    assert ok.status_code == 200
    assert client.get(f"{API}/users/me", headers=headers).status_code == 401  # old token revoked
    assert client.post(f"{API}/auth/login", json={"email": email, "password": "Another123"}).status_code == 200


def test_export_and_delete_account(client):
    headers, _, email = register(client)
    client.post(f"{API}/transactions", json={"description": "x", "amount": "10", "type": "expense", "transaction_date": "2026-11-01"}, headers=headers)
    exp = client.get(f"{API}/users/me/export", headers=headers)
    assert exp.status_code == 200 and len(exp.json()["transactions"]) == 1
    r = client.request("DELETE", f"{API}/users/me", json={"password": "Secure123pass", "confirm": "DELETE"}, headers=headers)
    assert r.status_code == 204
    assert client.post(f"{API}/auth/login", json={"email": email, "password": "Secure123pass"}).status_code == 401


def test_health(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"
