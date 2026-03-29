import axios from "axios";

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || "https://xpensa-4kmt.onrender.com",
    headers: { "Content-Type": "application/json" },
});

// Attach JWT to every request automatically
api.interceptors.request.use((config) => {
    const token = useAuthStore.getState().token;
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Auto-logout on 401
api.interceptors.response.use(
    (res) => res,
    (error) => {
        if (error.response?.status === 401) {
            useAuthStore.getState().logout();
        }
        return Promise.reject(error);
    }
);

// Import after to avoid circular dep
import { useAuthStore } from "@/store/auth";

export default api;