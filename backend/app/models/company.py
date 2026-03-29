import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.approval_rule import ApprovalRule


class Company(SQLModel, table=True):
    __tablename__ = "companies"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    name: str = Field(max_length=255, index=True)
    country: str = Field(max_length=100)

    # ISO 4217 currency code — e.g. "INR", "USD", "EUR"
    # Auto-set from country during admin signup
    base_currency: str = Field(max_length=3, default="USD")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    users: list["User"] = Relationship(back_populates="company")
    approval_rules: list["ApprovalRule"] = Relationship(back_populates="company")