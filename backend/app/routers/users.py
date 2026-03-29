import uuid
from typing import Annotated
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.core.security import hash_password, generate_temp_password
from app.core.dependencies import CurrentAdmin, CurrentUser, DBSession
from app.models.user import User, UserRole
from app.schemas.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserOut,
    CreateUserResponse,
)

router = APIRouter()


@router.post(
    "/",
    response_model=CreateUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: Create a new employee or manager",
)
def create_user(
    payload: CreateUserRequest,
    current_user: CurrentAdmin,
    session: DBSession,
):
    """
    Admin creates a new user in their company.
    - Generates a temporary password
    - User must change password on first login (must_change_password=True)
    - In production: temp_password is emailed. For now it's returned in response.
    """
    # Prevent creating another admin via this endpoint
    if payload.role == UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create admin users via this endpoint",
        )

    # Check email uniqueness
    existing = session.exec(
        select(User).where(User.email == payload.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    temp_password = generate_temp_password()

    new_user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(temp_password),
        role=payload.role,
        company_id=current_user.company_id,
        must_change_password=True,
    )
    session.add(new_user)
    session.flush()

    return CreateUserResponse(
        user=UserOut.model_validate(new_user),
        temp_password=temp_password,
        message=f"Share this temporary password with {payload.full_name}. They must change it on first login.",
    )


@router.get(
    "/",
    response_model=list[UserOut],
    summary="Admin: List all users in company",
)
def list_users(
    current_user: CurrentAdmin,
    session: DBSession,
):
    """Returns all users belonging to the admin's company."""
    users = session.exec(
        select(User)
        .where(User.company_id == current_user.company_id)
        .order_by(User.created_at)
    ).all()
    return users


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Admin: Get a specific user",
)
def get_user(
    user_id: uuid.UUID,
    current_user: CurrentAdmin,
    session: DBSession,
):
    user = session.exec(
        select(User).where(
            User.id == user_id,
            User.company_id == current_user.company_id,
        )
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Admin: Update user (name / activate / deactivate)",
)
def update_user(
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    current_user: CurrentAdmin,
    session: DBSession,
):
    user = session.exec(
        select(User).where(
            User.id == user_id,
            User.company_id == current_user.company_id,
        )
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent admin from deactivating themselves
    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.is_active is not None:
        user.is_active = payload.is_active

    session.add(user)
    return user


@router.post(
    "/{user_id}/reset-password",
    response_model=CreateUserResponse,
    summary="Admin: Reset a user's password",
)
def reset_password(
    user_id: uuid.UUID,
    current_user: CurrentAdmin,
    session: DBSession,
):
    """Generates a new temp password for the user."""
    user = session.exec(
        select(User).where(
            User.id == user_id,
            User.company_id == current_user.company_id,
        )
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    temp_password = generate_temp_password()
    user.hashed_password = hash_password(temp_password)
    user.must_change_password = True
    session.add(user)

    return CreateUserResponse(
        user=UserOut.model_validate(user),
        temp_password=temp_password,
        message=f"Password reset. Share this new temporary password with {user.full_name}.",
    )