from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.core.database import get_session
from app.core.security import hash_password, verify_password, create_access_token
from app.core.dependencies import CurrentUser, DBSession
from app.models.company import Company
from app.models.user import User, UserRole
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RegisterResponse,
    TokenResponse,
    UserOut,
)
from pydantic import field_validator

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register company + admin account",
)
def register(payload: RegisterRequest, session: DBSession):
    """
    One-shot registration:
    1. Creates the company
    2. Creates the admin user linked to that company
    3. Returns JWT + user + company details
    """
    # Check email not already taken
    existing = session.exec(
        select(User).where(User.email == payload.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Create company
    company = Company(
        name=payload.company_name,
        country=payload.country,
        base_currency=payload.base_currency.upper(),
    )
    session.add(company)
    session.flush()  # flush to get company.id before creating user

    # Create admin user
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=UserRole.admin,
        company_id=company.id,
        must_change_password=False,  # Admin set their own password
    )
    session.add(user)
    session.flush()

    # Generate JWT with role + company_id embedded
    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "role": user.role.value,
            "company_id": str(company.id),
        },
    )

    return RegisterResponse(
        access_token=token,
        user=UserOut.model_validate(user),
        company=company,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get JWT token",
)
def login(payload: LoginRequest, session: DBSession):
    """
    Validates email + password, returns JWT.
    Works for all roles: admin, manager, employee.
    """
    user = session.exec(
        select(User).where(User.email == payload.email)
    ).first()

    # Use constant-time comparison to prevent timing attacks
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your admin.",
        )

    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "role": user.role.value,
            "company_id": str(user.company_id),
        },
    )

    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current logged-in user",
)
def get_me(current_user: CurrentUser):
    """Returns the profile of whoever owns the JWT token."""
    return current_user

from pydantic import BaseModel

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change your own password",
)
def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    session: DBSession,
):
    """
    Used by any user (especially on first login when must_change_password=True).
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.must_change_password = False
    session.add(current_user)

    return {"message": "Password changed successfully"}