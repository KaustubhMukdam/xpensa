"""
Approval Engine — the core business logic of xpensa.

Two main entry points:
  - initialize_chain(expense_id, session): called when an expense is submitted
  - process_action(expense_id, approver_id, action, comment, session): called on approve/reject
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Session, select

from app.models.expense import Expense, ApprovalRecord, ExpenseStatus, ApprovalAction
from app.models.approval_rule import ApprovalRule, ApprovalStep
from app.models.user import User


def initialize_chain(expense: Expense, session: Session) -> None:
    """
    Called when an expense transitions from draft → pending.

    Finds the ApprovalRule for this expense's category + company,
    then creates the first pending ApprovalRecord in the chain.

    If no rule is found, auto-approve the expense (no approvers configured).
    """
    # Find matching rule (active, for this company + category)
    rule = session.exec(
        select(ApprovalRule).where(
            ApprovalRule.company_id == expense.company_id,
            ApprovalRule.category == expense.category,
            ApprovalRule.is_active == True,  # noqa: E712
        )
    ).first()

    if not rule:
        # No rule configured — auto-approve
        expense.status = ExpenseStatus.approved
        session.add(expense)
        return

    if rule.manager_is_approver:
        # Find the employee's direct manager (manager role in same company)
        # Simplified: use the first manager in the company
        manager = session.exec(
            select(User).where(
                User.company_id == expense.company_id,
                User.role == "manager",
                User.is_active == True,  # noqa: E712
            )
        ).first()

        if manager:
            record = ApprovalRecord(
                expense_id=expense.id,
                approver_id=manager.id,
                step_order=0,  # Step 0 = manager pre-step
                action=None,  # Pending
            )
            session.add(record)
            return  # Manager must act first; after that, proceed with numbered steps

    # Get ordered steps for the rule
    steps = session.exec(
        select(ApprovalStep)
        .where(ApprovalStep.rule_id == rule.id)
        .order_by(ApprovalStep.step_order)
    ).all()

    if not steps:
        # Rule exists but has no steps — auto-approve
        expense.status = ExpenseStatus.approved
        session.add(expense)
        return

    # Create pending record for Step 1
    first_step = steps[0]
    record = ApprovalRecord(
        expense_id=expense.id,
        approver_id=first_step.approver_id,
        step_order=first_step.step_order,
        action=None,
    )
    session.add(record)


def process_action(
    expense: Expense,
    approver_id: uuid.UUID,
    action: ApprovalAction,
    comment: Optional[str],
    session: Session,
) -> dict:
    """
    Called when an approver takes action (approve/reject) on an expense.

    Returns a dict with the updated expense status and a message.
    Raises ValueError if the approver is not the current pending approver.
    """
    # Find the current pending record for this expense
    pending_record = session.exec(
        select(ApprovalRecord).where(
            ApprovalRecord.expense_id == expense.id,
            ApprovalRecord.action == None,  # noqa: E711
        )
    ).first()

    if not pending_record:
        raise ValueError("No pending approval record found for this expense")

    if pending_record.approver_id != approver_id:
        raise ValueError("You are not the current pending approver for this expense")

    # Record the action
    pending_record.action = action
    pending_record.comment = comment
    pending_record.acted_at = datetime.now(timezone.utc)
    session.add(pending_record)

    if action == ApprovalAction.reject:
        expense.status = ExpenseStatus.rejected
        session.add(expense)
        return {"status": expense.status, "message": "Expense rejected"}

    # ── action == APPROVE ──────────────────────────────────────────────────────
    # Check conditional rules
    rule = session.exec(
        select(ApprovalRule).where(
            ApprovalRule.company_id == expense.company_id,
            ApprovalRule.category == expense.category,
            ApprovalRule.is_active == True,  # noqa: E712
        )
    ).first()

    if rule:
        # Specific approver shortcut — if THIS approver is the specific_approver, auto-approve
        if rule.specific_approver_id and rule.specific_approver_id == approver_id:
            expense.status = ExpenseStatus.approved
            session.add(expense)
            return {"status": expense.status, "message": "Expense approved (specific approver shortcut)"}

        # Percentage rule — check if enough approvers have approved
        if rule.min_approval_percentage:
            all_records = session.exec(
                select(ApprovalRecord).where(
                    ApprovalRecord.expense_id == expense.id,
                    ApprovalRecord.action != None,  # noqa: E711
                )
            ).all()
            total_steps = session.exec(
                select(ApprovalStep).where(ApprovalStep.rule_id == rule.id)
            ).all()
            if rule.manager_is_approver:
                total_count = len(total_steps) + 1  # +1 for manager
            else:
                total_count = len(total_steps)

            approved_count = sum(1 for r in all_records if r.action == ApprovalAction.approve)
            approval_pct = (approved_count / total_count * 100) if total_count > 0 else 100

            if approval_pct >= rule.min_approval_percentage:
                expense.status = ExpenseStatus.approved
                session.add(expense)
                return {"status": expense.status, "message": f"Expense approved ({approval_pct:.0f}% approval threshold met)"}

    # Try to advance to next step
    next_record = _get_next_step(expense, pending_record, rule, session)
    if next_record:
        session.add(next_record)
        return {"status": expense.status, "message": "Approved — forwarded to next approver"}
    else:
        # No more steps — fully approved
        expense.status = ExpenseStatus.approved
        session.add(expense)
        return {"status": expense.status, "message": "Expense fully approved"}


def _get_next_step(
    expense: Expense,
    current_record: ApprovalRecord,
    rule: Optional[ApprovalRule],
    session: Session,
) -> Optional[ApprovalRecord]:
    """
    Returns the next ApprovalRecord to create, or None if the chain is complete.
    """
    if not rule:
        return None

    # If current step was manager pre-step (step_order=0), go to Step 1
    if current_record.step_order == 0:
        steps = session.exec(
            select(ApprovalStep)
            .where(ApprovalStep.rule_id == rule.id)
            .order_by(ApprovalStep.step_order)
        ).all()
        if steps:
            return ApprovalRecord(
                expense_id=expense.id,
                approver_id=steps[0].approver_id,
                step_order=steps[0].step_order,
                action=None,
            )
        return None

    # Find next numbered step
    next_steps = session.exec(
        select(ApprovalStep)
        .where(
            ApprovalStep.rule_id == rule.id,
            ApprovalStep.step_order > current_record.step_order,
        )
        .order_by(ApprovalStep.step_order)
    ).all()

    if next_steps:
        return ApprovalRecord(
            expense_id=expense.id,
            approver_id=next_steps[0].approver_id,
            step_order=next_steps[0].step_order,
            action=None,
        )
    return None
