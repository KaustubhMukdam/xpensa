import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.expense import ExpenseStatus, ApprovalAction


class ExpenseCreate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    expense_date: date
    paid_by: str = Field(default="employee")


class ExpenseUpdate(BaseModel):
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    amount: Optional[float] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    expense_date: Optional[date] = None
    paid_by: Optional[str] = None


class ApprovalRecordOut(BaseModel):
    id: uuid.UUID
    approver_id: uuid.UUID
    approver_name: Optional[str] = None
    action: Optional[ApprovalAction]
    comment: Optional[str]
    step_order: int
    acted_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ExpenseOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    employee_id: uuid.UUID
    amount: float
    currency: str
    converted_amount: Optional[float]
    base_currency: Optional[str]
    exchange_rate_snapshot: Optional[float]
    category: str
    description: str
    expense_date: date
    paid_by: str
    status: ExpenseStatus
    receipt_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExpenseDetail(ExpenseOut):
    """Expense with full approval trail."""
    approval_trail: list[ApprovalRecordOut] = []
