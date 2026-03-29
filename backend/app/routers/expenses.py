import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query
from sqlmodel import select

from app.core.dependencies import CurrentUser, DBSession
from app.models.expense import Expense, ApprovalRecord, ExpenseStatus
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseOut, ExpenseDetail, ApprovalRecordOut
from app.services.currency import convert_amount
from app.services.approval_engine import initialize_chain

import asyncio

router = APIRouter()


def _build_expense_detail(expense: Expense, session) -> ExpenseDetail:
    """Helper to build ExpenseDetail with annotated approval trail."""
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

    return ExpenseDetail(
        **expense.model_dump(),
        approval_trail=trail,
    )


@router.post(
    "/",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Employee: Create a new expense (draft)",
)
def create_expense(
    payload: ExpenseCreate,
    current_user: CurrentUser,
    session: DBSession,
):
    """Creates a new draft expense. Currency conversion happens on submit, not here."""
    expense = Expense(
        company_id=current_user.company_id,
        employee_id=current_user.id,
        amount=payload.amount,
        currency=payload.currency.upper(),
        category=payload.category,
        description=payload.description,
        expense_date=payload.expense_date,
        paid_by=payload.paid_by,
        status=ExpenseStatus.draft,
    )
    session.add(expense)
    session.flush()
    session.refresh(expense)
    return expense


@router.get(
    "/",
    response_model=list[ExpenseOut],
    summary="Employee: List own expenses",
)
def list_expenses(
    current_user: CurrentUser,
    session: DBSession,
    status_filter: Optional[str] = Query(default=None, alias="status"),
):
    """
    Returns the current user's own expenses.
    Admins and managers see all expenses in their company.
    """
    from app.models.user import UserRole

    query = select(Expense)

    if current_user.role == UserRole.employee:
        query = query.where(Expense.employee_id == current_user.id)
    else:
        # Manager/Admin: see all company expenses
        query = query.where(Expense.company_id == current_user.company_id)

    if status_filter:
        try:
            status_enum = ExpenseStatus(status_filter)
            query = query.where(Expense.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{status_filter}'. Valid: draft, pending, approved, rejected",
            )

    return session.exec(query.order_by(Expense.created_at.desc())).all()


@router.get(
    "/{expense_id}",
    response_model=ExpenseDetail,
    summary="Get expense detail with approval trail",
)
def get_expense(
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
):
    from app.models.user import UserRole

    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    # Employees can only see their own; managers/admins can see company's
    if current_user.role == UserRole.employee and expense.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if current_user.role != UserRole.employee and expense.company_id != current_user.company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _build_expense_detail(expense, session)


@router.patch(
    "/{expense_id}",
    response_model=ExpenseOut,
    summary="Employee: Update a draft expense",
)
def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    current_user: CurrentUser,
    session: DBSession,
):
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if expense.status != ExpenseStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft expenses can be edited",
        )

    if payload.category is not None:
        expense.category = payload.category
    if payload.description is not None:
        expense.description = payload.description
    if payload.amount is not None:
        expense.amount = payload.amount
    if payload.currency is not None:
        expense.currency = payload.currency.upper()
    if payload.expense_date is not None:
        expense.expense_date = payload.expense_date
    if payload.paid_by is not None:
        expense.paid_by = payload.paid_by

    expense.updated_at = datetime.now(timezone.utc)
    session.add(expense)
    session.flush()
    session.refresh(expense)
    return expense


@router.post(
    "/{expense_id}/submit",
    response_model=ExpenseOut,
    summary="Employee: Submit a draft expense for approval",
)
def submit_expense(
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
):
    """
    Transitions expense from draft → pending.
    Converts currency to company base currency.
    Initializes the approval chain.
    """
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if expense.status != ExpenseStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft expenses can be submitted",
        )

    # Get company base currency
    from app.models.company import Company
    company = session.get(Company, expense.company_id)
    base_currency = company.base_currency if company else "USD"

    # Convert currency (run async in sync context)
    try:
        converted, rate = asyncio.run(
            convert_amount(expense.amount, expense.currency, base_currency)
        )
    except Exception:
        converted, rate = expense.amount, 1.0

    expense.converted_amount = converted
    expense.base_currency = base_currency
    expense.exchange_rate_snapshot = rate
    expense.status = ExpenseStatus.pending
    expense.updated_at = datetime.now(timezone.utc)
    session.add(expense)
    session.flush()

    # Initialize approval chain
    initialize_chain(expense, session)

    session.flush()
    session.refresh(expense)
    return expense
