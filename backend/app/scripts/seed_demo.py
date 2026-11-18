"""Create a demo account with SYNTHETIC data (never real bank data).

Usage:  python -m app.scripts.seed_demo [--reset]
Credentials: DEMO_EMAIL / DEMO_PASSWORD env vars, defaulting to demo@example.com / DemoPass123
"""
import os
import random
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User
from app.services import budgets, savings, transactions
from app.services.categories import category_by_slug, ensure_default_categories
from app.services.money import add_months, month_start

EMAIL = os.environ.get("DEMO_EMAIL", "demo@example.com")
PASSWORD = os.environ.get("DEMO_PASSWORD", "DemoPass123")

MONTHLY = [  # description, slug, low, high, times per month
    ("Groceries - DMart", "food", 900, 1800, 3), ("Swiggy order", "food", 250, 650, 4), ("Cafe Coffee", "food", 150, 320, 3),
    ("Uber ride", "transportation", 180, 450, 5), ("Metro recharge", "transportation", 500, 500, 1),
    ("Amazon purchase", "shopping", 600, 3200, 2), ("PVR movie tickets", "entertainment", 400, 900, 1),
    ("Electricity bill", "utilities", 1100, 1900, 1), ("Airtel broadband", "utilities", 799, 799, 1),
    ("Netflix subscription", "subscriptions", 649, 649, 1), ("Spotify premium", "subscriptions", 119, 119, 1),
    ("Apollo pharmacy", "healthcare", 200, 900, 1), ("Udemy course", "education", 449, 799, 0.4),
]


def main(reset: bool) -> None:
    rnd = random.Random(42)
    db = SessionLocal()
    ensure_default_categories(db)
    existing = db.scalar(select(User).where(User.email == EMAIL))
    if existing and not reset:
        print(f"Demo user already exists: {EMAIL} (use --reset to recreate)")
        return
    if existing:
        db.delete(existing)
        db.commit()
    user = User(email=EMAIL, full_name="Aarav Demo", password_hash=hash_password(PASSWORD), currency="INR")
    db.add(user)
    db.commit()
    today = date.today()
    first = add_months(month_start(today), -5)
    for i in range(6):
        m = add_months(first, i)
        last_day = today.day if m == month_start(today) else 28
        cat = category_by_slug(db, user.id, "income")
        transactions.create_transaction(db, user.id, description="Salary - Acme Pvt Ltd", amount=Decimal("85000"), tx_type="income",
                                        transaction_date=m, category_id=cat.id, commit=False)
        transactions.create_transaction(db, user.id, description="House rent", amount=Decimal("22000"), tx_type="expense",
                                        transaction_date=m + timedelta(days=1), category_id=category_by_slug(db, user.id, "housing").id, commit=False)
        for desc, slug, lo, hi, times in MONTHLY:
            n = int(times) + (1 if rnd.random() < times % 1 else 0)
            for _ in range(n):
                d = m + timedelta(days=rnd.randint(1, max(1, last_day - 1)))
                amt = Decimal(rnd.randint(lo, hi)) + Decimal(rnd.choice(["0", "0.50", "0.99"]))
                transactions.create_transaction(db, user.id, description=desc, amount=amt, tx_type="expense", transaction_date=d,
                                                category_id=category_by_slug(db, user.id, slug).id, payment_method=rnd.choice(["UPI", "Card", "Cash"]), commit=False)
        transactions.create_transaction(db, user.id, description="SIP - Index fund", amount=Decimal("10000"), tx_type="expense",
                                        transaction_date=m + timedelta(days=4), category_id=category_by_slug(db, user.id, "investments").id, commit=False)
    db.commit()
    cur = month_start(today)
    for slug, amt in [("food", 9000), ("transportation", 3000), ("shopping", 4000), ("entertainment", 1500), ("utilities", 3000), ("subscriptions", 800)]:
        budgets.create_budget(db, user.id, category_by_slug(db, user.id, slug).id, cur, Decimal(amt))
    savings.create_goal(db, user.id, "New laptop", Decimal("60000"), Decimal("20000"), add_months(today, 8))
    savings.create_goal(db, user.id, "Goa trip", Decimal("35000"), Decimal("12000"), add_months(today, 5))
    savings.create_goal(db, user.id, "Emergency fund", Decimal("200000"), Decimal("90000"), add_months(today, 18))
    print(f"Demo data created for {EMAIL}")


if __name__ == "__main__":
    main("--reset" in sys.argv)
