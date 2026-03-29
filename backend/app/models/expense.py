import uuid
from datetime import datetime, timezone, date
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.models.user import User


class ExpenseStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ApprovalAction(str, Enum):
    approve = "approve"
    reject = "reject"


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )

    company_id: uuid.UUID = Field(foreign_key="companies.id", index=True)
    employee_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # Amount in the currency the employee chose
    amount: float = Field(gt=0)
    currency: str = Field(max_length=3)  # ISO 4217, e.g. "USD"

    # Converted amount in the company's base currency (auto-calculated on submit)
    converted_amount: Optional[float] = Field(default=None)
    base_currency: Optional[str] = Field(default=None, max_length=3)

    # Snapshot of the exchange rate used at time of conversion
    exchange_rate_snapshot: Optional[float] = Field(default=None)

    # Expense details
    category: str = Field(max_length=100, index=True)
    description: str = Field(max_length=1000)
    expense_date: date = Field()
    paid_by: str = Field(max_length=50, default="employee")  # "employee" or "company"

    status: ExpenseStatus = Field(default=ExpenseStatus.draft, index=True)

    # Supabase Storage URL to uploaded receipt image
    receipt_url: Optional[str] = Field(default=None, max_length=1000)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    employee: Optional["User"] = Relationship(
        back_populates="expenses",
        sa_relationship_kwargs={"foreign_keys": "[Expense.employee_id]"},
    )
    approval_records: list["ApprovalRecord"] = Relationship(back_populates="expense")


class ApprovalRecord(SQLModel, table=True):
    """
    One row per approval action taken on an expense.
    Also used to track PENDING state (action=None) — i.e., who is next in the chain.
    """
    __tablename__ = "approval_records"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )

    expense_id: uuid.UUID = Field(foreign_key="expenses.id", index=True)
    approver_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # None = pending (waiting for action), "approve"/"reject" = action taken
    action: Optional[ApprovalAction] = Field(default=None)

    comment: Optional[str] = Field(default=None, max_length=1000)

    # Step in the approval chain (1-based)
    step_order: int = Field(default=1)

    # Exchange rate snapshot at time of action (set when action is taken)
    exchange_rate_snapshot: Optional[float] = Field(default=None)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    acted_at: Optional[datetime] = Field(default=None)

    # ─── Relationships ────────────────────────────────────────────────────────
    expense: Optional["Expense"] = Relationship(back_populates="approval_records")
    approver: Optional["User"] = Relationship(
        back_populates="approval_records",
        sa_relationship_kwargs={"foreign_keys": "[ApprovalRecord.approver_id]"},
    )
