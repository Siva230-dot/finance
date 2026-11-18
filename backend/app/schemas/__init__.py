"""Pydantic request/response schemas. Money is Decimal and serialised as a string."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

MoneyIn = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
SUPPORTED_CURRENCIES = ["INR", "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "AED", "CHF"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- auth / users ----------------
class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    currency: Currency = "INR"

    @field_validator("password")
    @classmethod
    def _strong(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Password must contain letters and numbers")
        return v

    @field_validator("full_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    currency: str
    theme_preference: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    currency: Currency | None = None
    theme_preference: Literal["light", "dark", "system"] | None = None

    @field_validator("currency")
    @classmethod
    def _supported(cls, v):
        if v is not None and v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency must be one of {', '.join(SUPPORTED_CURRENCIES)}")
        return v


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _strong(cls, v: str) -> str:
        return RegisterIn._strong(v)


class AccountDeleteIn(BaseModel):
    password: str
    confirm: Literal["DELETE"]


# ---------------- categories ----------------
class CategoryOut(ORM):
    id: uuid.UUID
    name: str
    slug: str
    kind: str
    color: str | None
    icon: str | None
    is_system: bool


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    kind: Literal["income", "expense", "both"] = "expense"
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


# ---------------- transactions ----------------
TxType = Literal["income", "expense"]
Recurrence = Literal["weekly", "monthly", "yearly"]


class TransactionIn(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    amount: MoneyIn
    type: TxType
    category_id: uuid.UUID | None = None
    transaction_date: date
    payment_method: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    is_recurring: bool = False
    recurrence_interval: Recurrence | None = None


class TransactionUpdateIn(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=255)
    amount: MoneyIn | None = None
    type: TxType | None = None
    category_id: uuid.UUID | None = None
    transaction_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    is_recurring: bool | None = None
    recurrence_interval: Recurrence | None = None


class TransactionOut(ORM):
    id: uuid.UUID
    description: str
    amount: Decimal
    type: str
    category: CategoryOut
    transaction_date: date
    payment_method: str | None
    notes: str | None
    is_recurring: bool
    recurrence_interval: str | None
    categorization_source: str
    categorization_confidence: Decimal | None
    created_at: datetime
    updated_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int


# ---------------- budgets ----------------
class BudgetIn(BaseModel):
    category_id: uuid.UUID
    month: date
    amount: MoneyIn
    notes: str | None = Field(default=None, max_length=500)


class BudgetUpdateIn(BaseModel):
    amount: MoneyIn | None = None
    notes: str | None = Field(default=None, max_length=500)


class BudgetOut(ORM):
    id: uuid.UUID
    category: CategoryOut
    month: date
    amount: Decimal
    notes: str | None
    spent: Decimal = Decimal("0")
    remaining: Decimal = Decimal("0")
    utilization: Decimal = Decimal("0")
    status: str = "on_track"


class RecommendationOut(ORM):
    id: uuid.UUID
    category: CategoryOut
    month: date
    proposed_amount: Decimal
    historical_basis: dict
    reason: str
    expected_effect: str
    confidence: str
    limitations: str | None
    status: str
    created_at: datetime


# ---------------- savings ----------------
class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: MoneyIn
    current_amount: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)] = Decimal("0")
    target_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class GoalUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    target_amount: MoneyIn | None = None
    target_date: date | None = None
    status: Literal["active", "completed", "archived"] | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ContributionIn(BaseModel):
    amount: Annotated[Decimal, Field(max_digits=14, decimal_places=2)]
    contribution_date: date | None = None
    note: str | None = Field(default=None, max_length=255)

    @field_validator("amount")
    @classmethod
    def _nonzero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("Contribution amount cannot be zero")
        return v


class ContributionOut(ORM):
    id: uuid.UUID
    amount: Decimal
    contribution_date: date
    note: str | None
    created_at: datetime


class GoalOut(ORM):
    id: uuid.UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    target_date: date | None
    status: str
    notes: str | None
    created_at: datetime
    remaining_amount: Decimal = Decimal("0")
    progress_percent: Decimal = Decimal("0")
    months_remaining: int | None = None
    required_monthly: Decimal | None = None
    on_track: bool | None = None
    contributions: list[ContributionOut] = []


# ---------------- uploads ----------------
class PreviewRow(BaseModel):
    index: int
    transaction_date: date
    description: str
    amount: Decimal
    type: TxType
    category_slug: str
    category_name: str
    categorization_source: str
    confidence: Decimal
    is_duplicate: bool
    duplicate_reason: str | None = None


class UploadPreviewOut(BaseModel):
    upload_id: uuid.UUID
    filename: str
    file_type: str
    rows: list[PreviewRow]
    duplicates: int
    warnings: list[str] = []


class ImportApproveIn(BaseModel):
    selected_indexes: list[int] = Field(min_length=1, max_length=5000)
    category_overrides: dict[int, uuid.UUID] = {}


class ImportResultOut(BaseModel):
    upload_id: uuid.UUID
    imported: int
    skipped: int


# ---------------- assistant ----------------
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    meta: dict | None = None
    created_at: datetime


class ChatOut(BaseModel):
    conversation_id: uuid.UUID
    message: ChatMessageOut


class ConversationOut(ORM):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
