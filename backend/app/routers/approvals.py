import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from pydantic import BaseModel

from app.core.dependencies import CurrentUser, CurrentManager, DBSession
from app.models.expense import Expense, ApprovalRecord, ExpenseStatus, ApprovalAction
from app.models.user import User, UserRole
from app.schemas.expense import ExpenseDetail, ApprovalRecordOut
from app.services.approval_engine import process_action

router = APIRouter()


class ApprovalActionRequest(BaseModel):
    comment: Optional[str] = None


def _build_expense_detail(expense: Expense, session) -> ExpenseDetail:
    records = session.exec(
        select(ApprovalRecord)
        .where(ApprovalRecord.expense_id == expense.id)
        .order_by(ApprovalRecord.step_order)
    ).all()

    trail = []
    for r in records:
        approver = session.get(User, r.approver_id)
        trail.append(ApprovalRecordOut(
            id=r.id,
            approver_id=r.approver_id,
            approver_name=approver.full_name if approver else None,
            action=r.action,
            comment=r.comment,
            step_order=r.step_order,
            acted_at=r.acted_at,
        ))

    from app.schemas.expense import ExpenseDetail
    return ExpenseDetail(
        **expense.model_dump(),
        approval_trail=trail,
    )


@router.get(
    "/",
    response_model=list[ExpenseDetail],
    summary="Manager/Admin: Get pending approval queue",
)
def list_pending_approvals(
    current_user: CurrentManager,
    session: DBSession,
):
    """
    Returns all expenses where the current user is the active pending approver.
    Also allows admins to see all pending expenses in their company.
    """
    if current_user.role == UserRole.admin:
        # Admin sees all pending expenses in company
        expenses = session.exec(
            select(Expense).where(
                Expense.company_id == current_user.company_id,
                Expense.status == ExpenseStatus.pending,
            )
        ).all()
    else:
        # Manager sees only expenses where they are the current pending approver
        pending_record_subq = session.exec(
            select(ApprovalRecord.expense_id).where(
                ApprovalRecord.approver_id == current_user.id,
                ApprovalRecord.action == None,  # noqa: E711
            )
        ).all()
        expense_ids = [r for r in pending_record_subq]

        if not expense_ids:
            return []

        expenses = session.exec(
            select(Expense).where(
                Expense.id.in_(expense_ids),
                Expense.status == ExpenseStatus.pending,
            )
        ).all()

    return [_build_expense_detail(e, session) for e in expenses]


@router.get(
    "/{expense_id}",
    response_model=ExpenseDetail,
    summary="Manager/Admin: Get expense detail for approval",
)
def get_approval_detail(
    expense_id: uuid.UUID,
    current_user: CurrentManager,
    session: DBSession,
):
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.company_id != current_user.company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _build_expense_detail(expense, session)


@router.post(
    "/{expense_id}/approve",
    response_model=ExpenseDetail,
    summary="Manager: Approve an expense",
)
def approve_expense(
    expense_id: uuid.UUID,
    payload: ApprovalActionRequest,
    current_user: CurrentManager,
    session: DBSession,
):
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.status != ExpenseStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expense is not pending approval (status: {expense.status.value})",
        )

    try:
        process_action(
            expense=expense,
            approver_id=current_user.id,
            action=ApprovalAction.approve,
            comment=payload.comment,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    session.flush()
    session.refresh(expense)
    return _build_expense_detail(expense, session)


@router.post(
    "/{expense_id}/reject",
    response_model=ExpenseDetail,
    summary="Manager: Reject an expense",
)
def reject_expense(
    expense_id: uuid.UUID,
    payload: ApprovalActionRequest,
    current_user: CurrentManager,
    session: DBSession,
):
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.status != ExpenseStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expense is not pending approval (status: {expense.status.value})",
        )

    try:
        process_action(
            expense=expense,
            approver_id=current_user.id,
            action=ApprovalAction.reject,
            comment=payload.comment,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    session.flush()
    session.refresh(expense)
    return _build_expense_detail(expense, session)
