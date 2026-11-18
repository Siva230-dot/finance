import os

os.environ["APP_ENV"] = "test"
test_url = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/financemate_test")
os.environ["DATABASE_URL"] = test_url
os.environ["GROQ_API_KEY"] = ""
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-1234567890")

import itertools  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.agents import llm as llm_module  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

USER_TABLES = ["audit_logs", "pending_confirmations", "agent_messages", "agent_conversations", "uploaded_files", "financial_reports",
               "budget_recommendations", "savings_contributions", "savings_goals", "budgets", "transactions"]


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    os.environ["ALEMBIC_DATABASE_URL"] = test_url
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean():
    yield
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(USER_TABLES)} CASCADE"))
        conn.execute(text("DELETE FROM categories WHERE user_id IS NOT NULL"))
        conn.execute(text("DELETE FROM users"))
    llm_module.provider = llm_module._groq


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


_counter = itertools.count()


def register(client, name="Asha Rao", currency="INR"):
    email = f"user{next(_counter)}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "full_name": name, "password": "Secure123pass", "currency": currency})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, r.json()["user"], email


@pytest.fixture
def auth(client):
    headers, user, _ = register(client)
    return headers


@pytest.fixture
def other_auth(client):
    headers, user, _ = register(client, name="Other Person")
    return headers


def categories(client, headers) -> dict[str, str]:
    return {c["slug"]: c["id"] for c in client.get("/api/v1/categories", headers=headers).json()}


def add_tx(client, headers, description="Groceries", amount="500.00", type="expense", date="2026-11-05", category_id=None, **extra):
    body = {"description": description, "amount": amount, "type": type, "transaction_date": date, **extra}
    if category_id:
        body["category_id"] = category_id
    r = client.post("/api/v1/transactions", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


class ScriptedLLM:
    """Deterministic stand-in for ChatGroq: returns scripted AIMessages and records what it saw."""

    def __init__(self, responses=None, intent=None, raise_exc=None):
        self.responses = list(responses or [])
        self.intent = intent
        self.raise_exc = raise_exc
        self.calls = []
        self.bound_tools = []

    def bind_tools(self, tools):
        self.bound_tools.append([t.name for t in tools])
        return self

    def invoke(self, messages, *args, **kwargs):
        if self.raise_exc:
            raise self.raise_exc
        if isinstance(messages, list) and len(messages) == 1 and "Classify the user's request" in str(messages[0].content):
            return AIMessage(content='{"intent": "%s"}' % (self.intent or "general"))
        if isinstance(messages, str):
            return AIMessage(content="[]")
        self.calls.append(messages)
        if not self.responses:
            return AIMessage(content="(no more scripted responses)")
        r = self.responses.pop(0)
        return r(messages) if callable(r) else r


def tool_call(name, args, call_id=None):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id or f"call_{name}_{next(_counter)}"}])


@pytest.fixture
def fake_llm():
    def install(*responses, intent=None, raise_exc=None):
        fake = ScriptedLLM(responses, intent=intent, raise_exc=raise_exc)
        llm_module.provider = lambda: fake
        return fake

    return install
