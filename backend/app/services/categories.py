"""Category lookup and rule-based (+ optional LLM-assisted) categorization."""
import json
import logging
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category

logger = logging.getLogger("financemate.categorize")

# name, slug, kind, color
DEFAULT_CATEGORIES: list[tuple[str, str, str, str]] = [
    ("Income", "income", "income", "#5A6751"),
    ("Food and Groceries", "food", "expense", "#A58B58"),
    ("Housing", "housing", "expense", "#574637"),
    ("Transportation", "transportation", "expense", "#25382D"),
    ("Healthcare", "healthcare", "expense", "#8C6E5A"),
    ("Shopping", "shopping", "expense", "#B4846C"),
    ("Entertainment", "entertainment", "expense", "#7D6B91"),
    ("Education", "education", "expense", "#4F6D7A"),
    ("Utilities", "utilities", "expense", "#6B7F5E"),
    ("Subscriptions", "subscriptions", "expense", "#9A7B4F"),
    ("Travel", "travel", "expense", "#3F5E5A"),
    ("Investments", "investments", "both", "#7A6A3A"),
    ("Savings", "savings", "both", "#506B4E"),
    ("Other", "other", "both", "#8A8577"),
]

# Ordered keyword rules: first match wins. Patterns are word-boundary regexes on lowercased text.
RULES: list[tuple[str, list[str]]] = [
    ("income", ["salary", "payroll", "stipend", "bonus", "refund", "interest credit", "dividend", "freelance", "invoice paid", "cashback", "credited by"]),
    ("subscriptions", ["netflix", "spotify", "prime", "hotstar", "youtube premium", "subscription", "icloud", "google one", "chatgpt", "adobe", "zee5", "sonyliv"]),
    ("food", ["grocery", "groceries", "swiggy", "zomato", "restaurant", "cafe", "coffee", "starbucks", "bigbasket", "blinkit", "zepto", "dmart", "food", "lunch", "dinner", "breakfast", "bakery", "supermarket", "milk", "vegetables", "dominos", "pizza", "mcdonald", "kfc"]),
    ("transportation", ["uber", "ola", "rapido", "metro", "petrol", "fuel", "diesel", "bus", "auto", "taxi", "cab", "parking", "toll", "fastag", "train ticket", "irctc"]),
    ("travel", ["flight", "airline", "indigo", "air india", "vistara", "hotel", "airbnb", "makemytrip", "goibibo", "booking.com", "trip", "vacation", "holiday"]),
    ("housing", ["rent", "maintenance", "society", "mortgage", "home loan", "emi house", "landlord", "plumber", "electrician", "furniture"]),
    ("utilities", ["electricity", "water bill", "gas bill", "broadband", "wifi", "internet", "mobile recharge", "recharge", "airtel", "jio", "vodafone", "bsnl", "dth", "power bill"]),
    ("healthcare", ["pharmacy", "medicine", "hospital", "doctor", "clinic", "apollo", "medplus", "health", "dental", "insurance premium", "lab test", "1mg", "pharmeasy"]),
    ("education", ["tuition", "course", "udemy", "coursera", "books", "school", "college", "exam fee", "university", "byju", "unacademy", "stationery"]),
    ("entertainment", ["movie", "cinema", "pvr", "inox", "bookmyshow", "concert", "game", "steam", "playstation", "bowling", "club"]),
    ("shopping", ["amazon", "flipkart", "myntra", "ajio", "mall", "clothes", "shoes", "electronics", "nykaa", "decathlon", "ikea", "shopping", "meesho"]),
    ("investments", ["mutual fund", "sip", "zerodha", "groww", "stocks", "nps", "ppf", "fixed deposit", "fd ", "upstox"]),
    ("savings", ["savings transfer", "to savings", "recurring deposit", "rd "]),
]
_COMPILED = [(slug, [re.compile(r"\b" + re.escape(k.strip()) + r"\b") for k in kws]) for slug, kws in RULES]


@dataclass
class CategoryGuess:
    slug: str
    source: str  # rule | llm | default
    confidence: Decimal


def list_categories(db: Session, user_id: uuid.UUID) -> list[Category]:
    return list(
        db.scalars(
            select(Category)
            .where(or_(Category.user_id.is_(None), Category.user_id == user_id))
            .order_by(Category.is_system.desc(), Category.name)
        )
    )


def get_category(db: Session, user_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    cat = db.get(Category, category_id)
    if not cat or (cat.user_id is not None and cat.user_id != user_id):
        raise AppError(404, "not_found", "Category not found")
    return cat


def resolve_category(db: Session, user_id: uuid.UUID, ref: str | uuid.UUID | None) -> Category | None:
    """Resolve by id, slug, or (case-insensitive, fuzzy) name among system + the user's categories."""
    if ref is None or ref == "":
        return None
    if isinstance(ref, uuid.UUID):
        return get_category(db, user_id, ref)
    s = str(ref).strip()
    try:
        return get_category(db, user_id, uuid.UUID(s))
    except ValueError:
        pass
    cats = list_categories(db, user_id)
    low = s.lower()
    for c in cats:
        if c.slug == low or c.name.lower() == low:
            return c
    aliases = {"groceries": "food", "grocery": "food", "food & groceries": "food", "dining": "food", "restaurant": "food",
               "transport": "transportation", "commute": "transportation", "rent": "housing", "bills": "utilities",
               "medical": "healthcare", "health": "healthcare", "fun": "entertainment", "salary": "income", "investment": "investments"}
    if low in aliases:
        return next((c for c in cats if c.slug == aliases[low]), None)
    for c in cats:  # partial match e.g. "food" -> "Food and Groceries"
        if low in c.name.lower() or c.name.lower().split()[0] == low.split()[0]:
            return c
    return None


def rule_categorize(description: str, tx_type: str | None = None) -> CategoryGuess | None:
    text = f" {description.lower()} "
    for slug, patterns in _COMPILED:
        hits = sum(1 for p in patterns if p.search(text))
        if hits:
            if slug == "income" and tx_type == "expense":
                continue
            conf = Decimal("0.90") if hits > 1 else Decimal("0.80")
            return CategoryGuess(slug, "rule", conf)
    return None


def llm_categorize(descriptions: list[str], llm) -> list[CategoryGuess | None]:
    """Ask the LLM to pick from the fixed category list. Output is validated; anything invalid is ignored."""
    if not descriptions or llm is None:
        return [None] * len(descriptions)
    slugs = [s for _, s, _, _ in DEFAULT_CATEGORIES]
    prompt = (
        "Classify each bank transaction description into exactly one category slug from this list: "
        f"{', '.join(slugs)}. Reply ONLY with a JSON array of objects {{\"i\": index, \"slug\": slug, \"confidence\": 0..1}}.\n"
        + "\n".join(f"{i}: {d[:120]}" for i, d in enumerate(descriptions))
    )
    try:
        raw = llm.invoke(prompt).content
        match = re.search(r"\[.*\]", raw if isinstance(raw, str) else str(raw), re.S)
        data = json.loads(match.group(0)) if match else []
    except Exception as exc:  # LLM failures must never break imports
        logger.warning("llm categorization failed: %s", type(exc).__name__)
        return [None] * len(descriptions)
    out: list[CategoryGuess | None] = [None] * len(descriptions)
    for item in data if isinstance(data, list) else []:
        try:
            i, slug = int(item["i"]), str(item["slug"])
            conf = Decimal(str(min(max(float(item.get("confidence", 0.6)), 0), 0.85))).quantize(Decimal("0.001"))
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= i < len(out) and slug in slugs:
            out[i] = CategoryGuess(slug, "llm", conf)  # LLM confidence capped: never treated as certain
    return out


def categorize_many(descriptions: list[str], types: list[str | None], llm=None) -> list[CategoryGuess]:
    guesses: list[CategoryGuess | None] = [rule_categorize(d, t) for d, t in zip(descriptions, types)]
    missing = [i for i, g in enumerate(guesses) if g is None]
    if missing and llm is not None:
        llm_out = llm_categorize([descriptions[i] for i in missing][:40], llm)
        for idx, g in zip(missing, llm_out):
            guesses[idx] = g
    result: list[CategoryGuess] = []
    for g, t in zip(guesses, types):
        if g is None:
            g = CategoryGuess("income" if t == "income" else "other", "default", Decimal("0.300"))
        result.append(g)
    return result


def category_by_slug(db: Session, user_id: uuid.UUID, slug: str) -> Category:
    cat = db.scalar(select(Category).where(Category.slug == slug, or_(Category.user_id.is_(None), Category.user_id == user_id)))
    if not cat:
        cat = db.scalar(select(Category).where(Category.slug == "other", Category.user_id.is_(None)))
    if not cat:
        raise AppError(500, "categories_missing", "Default categories are not seeded")
    return cat


def ensure_default_categories(db: Session) -> None:
    existing = {c.slug for c in db.scalars(select(Category).where(Category.user_id.is_(None)))}
    for name, slug, kind, color in DEFAULT_CATEGORIES:
        if slug not in existing:
            db.add(Category(name=name, slug=slug, kind=kind, color=color, is_system=True, user_id=None))
    db.commit()
