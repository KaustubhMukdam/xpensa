import { useAuthStore } from "@/store/auth";
export default function ManagerDashboard() {
    const { user } = useAuthStore();
    return <div className="p-8 text-foreground">Manager Dashboard — Welcome {user?.full_name}</div>;
}