import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class ApprovalRule(SQLModel, table=True):
    """
    One rule per expense category per company.
    e.g. "Miscellaneous expenses" rule for Acme Corp.

    The rule defines:
    - Which approvers are in the chain (via ApprovalStep)
    - Whether manager is always Step 1
    - Whether any single specific approver can auto-approve the whole thing
    - Minimum % of approvers needed (optional)
    """
    __tablename__ = "approval_rules"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )

    company_id: uuid.UUID = Field(foreign_key="companies.id", index=True)

    # e.g. "travel", "meals", "miscellaneous", "equipment"
    category: str = Field(max_length=100, index=True)

    description: Optional[str] = Field(default=None, max_length=500)

    # If True, the company manager is always injected as Step 1 automatically
    manager_is_approver: bool = Field(default=False)

    # If True: send approval request to ALL approvers at the same time.
    # If False (default): sequential — Step 1 must approve before Step 2 is notified.
    approvers_random: bool = Field(default=False)

    # Optional: if this specific user approves, the whole request is auto-approved
    # regardless of other steps
    specific_approver_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.id"
    )

    # Optional: minimum % of approvers that must approve
    # e.g. 60 means 60% of approvers must approve
    min_approval_percentage: Optional[int] = Field(default=None, ge=1, le=100)

    # Soft delete — keeps historical data intact
    is_active: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    company: Optional["Company"] = Relationship(back_populates="approval_rules")
    steps: list["ApprovalStep"] = Relationship(back_populates="rule")


class ApprovalStep(SQLModel, table=True):
    """
    One row per approver in a rule's chain.
    step_order=1 is notified first, then step_order=2, etc.
    """
    __tablename__ = "approval_steps"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )

    rule_id: uuid.UUID = Field(foreign_key="approval_rules.id", index=True)
    approver_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # 1-based ordering — Step 1 goes first
    step_order: int = Field(ge=1)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    rule: Optional["ApprovalRule"] = Relationship(back_populates="steps")
    approver: Optional["User"] = Relationship(back_populates="approval_steps")