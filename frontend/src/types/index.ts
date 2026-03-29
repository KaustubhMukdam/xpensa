export type UserRole = "admin" | "manager" | "employee";

export interface User {
    id: string;
    email: string;
    full_name: string;
    role: UserRole;
    company_id: string;
    is_active: boolean;
    must_change_password: boolean;
    created_at: string;
}

export interface Company {
    id: string;
    name: string;
    country: string;
    base_currency: string;
    created_at: string;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
    user: User;
}

export interface RegisterResponse {
    access_token: string;
    token_type: string;
    user: User;
    company: Company;
}