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

// ── sessionStorage keys ───────────────────────────────────────────────────────
const TOKEN_KEY = "xpensa_token";
const USER_KEY = "xpensa_user";

// ── Hydrate from sessionStorage on load ──────────────────────────────────────
// sessionStorage survives page refresh but is cleared when the tab is closed.
// This is intentionally more secure than localStorage for a JWT auth token.
function loadPersistedAuth(): { token: string | null; user: AuthUser | null } {
    try {
        const token = sessionStorage.getItem(TOKEN_KEY);
        const userRaw = sessionStorage.getItem(USER_KEY);
        if (token && userRaw) {
            const user = JSON.parse(userRaw) as AuthUser;
            return { token, user };
        }
    } catch {
        // Corrupt data — clear and start fresh
        sessionStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem(USER_KEY);
    }
    return { token: null, user: null };
}

const persisted = loadPersistedAuth();

export const useAuthStore = create<AuthState>((set) => ({
    token: persisted.token,
    user: persisted.user,
    isAuthenticated: persisted.token !== null,

    setAuth: (token, user) => {
        // Persist to sessionStorage
        try {
            sessionStorage.setItem(TOKEN_KEY, token);
            sessionStorage.setItem(USER_KEY, JSON.stringify(user));
        } catch {
            // sessionStorage might be disabled (e.g. incognito with strict settings)
            // Silently fall back to in-memory only
        }
        set({ token, user, isAuthenticated: true });
    },

    logout: () => {
        // Clear sessionStorage on explicit logout
        try {
            sessionStorage.removeItem(TOKEN_KEY);
            sessionStorage.removeItem(USER_KEY);
        } catch {
            // ignore
        }
        set({ token: null, user: null, isAuthenticated: false });
    },
}));