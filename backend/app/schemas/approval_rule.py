import uuid
from typing import Optional
from pydantic import BaseModel, Field


class ApprovalStepIn(BaseModel):
    approver_id: uuid.UUID
    step_order: int = Field(ge=1)


class ApprovalRuleCreate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    manager_is_approver: bool = False
    approvers_random: bool = False
    specific_approver_id: Optional[uuid.UUID] = None
    min_approval_percentage: Optional[int] = Field(default=None, ge=1, le=100)
    steps: list[ApprovalStepIn] = []


class ApprovalRuleUpdate(BaseModel):
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    manager_is_approver: Optional[bool] = None
    approvers_random: Optional[bool] = None
    specific_approver_id: Optional[uuid.UUID] = None
    min_approval_percentage: Optional[int] = Field(default=None, ge=1, le=100)
    steps: Optional[list[ApprovalStepIn]] = None


class ApprovalStepOut(BaseModel):
    id: uuid.UUID
    approver_id: uuid.UUID
    step_order: int

    model_config = {"from_attributes": True}


class ApprovalRuleOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    category: str
    description: Optional[str]
    manager_is_approver: bool
    approvers_random: bool
    specific_approver_id: Optional[uuid.UUID]
    min_approval_percentage: Optional[int]
    is_active: bool
    steps: list[ApprovalStepOut] = []

    model_config = {"from_attributes": True}
