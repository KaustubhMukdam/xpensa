import uuid
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.core.dependencies import CurrentAdmin, DBSession
from app.models.approval_rule import ApprovalRule, ApprovalStep
from app.schemas.approval_rule import (
    ApprovalRuleCreate,
    ApprovalRuleUpdate,
    ApprovalRuleOut,
)

router = APIRouter()


@router.post(
    "/",
    response_model=ApprovalRuleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: Create an approval rule with steps",
)
def create_approval_rule(
    payload: ApprovalRuleCreate,
    current_user: CurrentAdmin,
    session: DBSession,
):
    """Creates an approval rule for a category. Also creates all steps in order."""
    # Prevent duplicate active rules for same category
    existing = session.exec(
        select(ApprovalRule).where(
            ApprovalRule.company_id == current_user.company_id,
            ApprovalRule.category == payload.category,
            ApprovalRule.is_active == True,  # noqa: E712
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active rule for category '{payload.category}' already exists",
        )

    rule = ApprovalRule(
        company_id=current_user.company_id,
        category=payload.category,
        description=payload.description,
        manager_is_approver=payload.manager_is_approver,
        approvers_random=payload.approvers_random,
        specific_approver_id=payload.specific_approver_id,
        min_approval_percentage=payload.min_approval_percentage,
    )
    session.add(rule)
    session.flush()

    for step_data in payload.steps:
        step = ApprovalStep(
            rule_id=rule.id,
            approver_id=step_data.approver_id,
            step_order=step_data.step_order,
        )
        session.add(step)

    session.flush()
    session.refresh(rule)
    return rule


@router.get(
    "/",
    response_model=list[ApprovalRuleOut],
    summary="Admin: List all approval rules for company",
)
def list_approval_rules(
    current_user: CurrentAdmin,
    session: DBSession,
):
    rules = session.exec(
        select(ApprovalRule).where(
            ApprovalRule.company_id == current_user.company_id,
            ApprovalRule.is_active == True,  # noqa: E712
        )
    ).all()
    return rules


@router.get(
    "/{rule_id}",
    response_model=ApprovalRuleOut,
    summary="Admin: Get a specific approval rule",
)
def get_approval_rule(
    rule_id: uuid.UUID,
    current_user: CurrentAdmin,
    session: DBSession,
):
    rule = session.exec(
        select(ApprovalRule).where(
            ApprovalRule.id == rule_id,
            ApprovalRule.company_id == current_user.company_id,
        )
    ).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return rule


@router.patch(
    "/{rule_id}",
    response_model=ApprovalRuleOut,
    summary="Admin: Update an approval rule",
)
def update_approval_rule(
    rule_id: uuid.UUID,
    payload: ApprovalRuleUpdate,
    current_user: CurrentAdmin,
    session: DBSession,
):
    rule = session.exec(
        select(ApprovalRule).where(
            ApprovalRule.id == rule_id,
            ApprovalRule.company_id == current_user.company_id,
        )
    ).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    if payload.category is not None:
        rule.category = payload.category
    if payload.description is not None:
        rule.description = payload.description
    if payload.manager_is_approver is not None:
        rule.manager_is_approver = payload.manager_is_approver
    if payload.approvers_random is not None:
        rule.approvers_random = payload.approvers_random
    if payload.specific_approver_id is not None:
        rule.specific_approver_id = payload.specific_approver_id
    if payload.min_approval_percentage is not None:
        rule.min_approval_percentage = payload.min_approval_percentage

    # Replace steps if provided
    if payload.steps is not None:
        # Delete existing steps
        existing_steps = session.exec(
            select(ApprovalStep).where(ApprovalStep.rule_id == rule.id)
        ).all()
        for step in existing_steps:
            session.delete(step)
        session.flush()

        for step_data in payload.steps:
            step = ApprovalStep(
                rule_id=rule.id,
                approver_id=step_data.approver_id,
                step_order=step_data.step_order,
            )
            session.add(step)

    session.add(rule)
    session.flush()
    session.refresh(rule)
    return rule


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_200_OK,
    summary="Admin: Soft-delete an approval rule",
)
def delete_approval_rule(
    rule_id: uuid.UUID,
    current_user: CurrentAdmin,
    session: DBSession,
):
    rule = session.exec(
        select(ApprovalRule).where(
            ApprovalRule.id == rule_id,
            ApprovalRule.company_id == current_user.company_id,
        )
    ).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    rule.is_active = False
    session.add(rule)
    return {"message": f"Approval rule for '{rule.category}' deactivated"}
