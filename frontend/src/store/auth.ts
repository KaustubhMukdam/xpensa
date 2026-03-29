import { create } from "zustand";

export type UserRole = "admin" | "manager" | "employee";

export interface AuthUser {
    id: string;
    email: string;
    full_name: string;
    role: UserRole;
    company_id: string;
    is_active: boolean;
    must_change_password: boolean;
}

interface AuthState {
    token: string | null;
    user: AuthUser | null;
    isAuthenticated: boolean;
    setAuth: (token: string, user: AuthUser) => void;
    logout: () => void;
}

// In-memory store — no localStorage (keeps it simple + secure)
// Token is lost on page refresh → user must log in again (fine for hackathon)
export const useAuthStore = create<AuthState>((set) => ({
    token: null,
    user: null,
    isAuthenticated: false,

    setAuth: (token, user) =>
        set({ token, user, isAuthenticated: true }),

    logout: () =>
        set({ token: null, user: null, isAuthenticated: false }),
}));