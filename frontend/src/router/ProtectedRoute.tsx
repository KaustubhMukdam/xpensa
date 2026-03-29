import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import type { UserRole } from "@/store/auth";

interface Props {
    allowedRoles?: UserRole[];
}

export default function ProtectedRoute({ allowedRoles }: Props) {
    const { isAuthenticated, user } = useAuthStore();

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    if (allowedRoles && user && !allowedRoles.includes(user.role)) {
        // Redirect to their own dashboard if they hit a wrong role route
        return <Navigate to={ `/${user.role}` } replace />;
    }

    return <Outlet />;
}