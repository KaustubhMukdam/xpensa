import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
from app.models.user import UserRole


# ─── Request Schemas ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Admin signs up — creates company + first admin user in one shot."""
    # Company fields
    company_name: str
    country: str
    base_currency: str = "USD"

    # Admin user fields
    full_name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("base_currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ─── Response Schemas ─────────────────────────────────────────────────────────

class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    base_currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    company_id: uuid.UUID
    is_active: bool
    must_change_password: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    company: CompanyOut