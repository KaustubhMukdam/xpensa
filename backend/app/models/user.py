import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from enum import Enum
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.approval_rule import ApprovalStep
    from app.models.expense import Expense, ApprovalRecord


class UserRole(str, Enum):
    admin = "admin"
    manager = "manager"
    employee = "employee"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    email: str = Field(max_length=255, unique=True, index=True)
    full_name: str = Field(max_length=255)
    hashed_password: str = Field(max_length=255)

    role: UserRole = Field(default=UserRole.employee)

    # FK to Company
    company_id: uuid.UUID = Field(foreign_key="companies.id", index=True)

    is_active: bool = Field(default=True)

    # True = user signed up via temp password and must change it on first login
    must_change_password: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    company: Optional["Company"] = Relationship(back_populates="users")

    # Approval steps where this user is the designated approver
    approval_steps: list["ApprovalStep"] = Relationship(back_populates="approver")

    # Expenses submitted by this user (as employee)
    expenses: list["Expense"] = Relationship(
        back_populates="employee",
        sa_relationship_kwargs={"foreign_keys": "[Expense.employee_id]"},
    )

    # Approval records where this user acted as approver
    approval_records: list["ApprovalRecord"] = Relationship(
        back_populates="approver",
        sa_relationship_kwargs={"foreign_keys": "[ApprovalRecord.approver_id]"},
    )