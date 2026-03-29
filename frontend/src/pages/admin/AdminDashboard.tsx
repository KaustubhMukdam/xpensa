import { useAuthStore } from "@/store/auth";
export default function AdminDashboard() {
    const { user } = useAuthStore();
    return <div className="p-8 text-foreground">Admin Dashboard — Welcome {user?.full_name}</div>;
}