import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole  # "manager" or "employee" (admin cannot be created this way)


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


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


class CreateUserResponse(BaseModel):
    user: UserOut
    temp_password: str   # shown once — frontend should display it to admin
    message: str