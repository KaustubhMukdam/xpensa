import { useAuthStore } from "@/store/auth";
export default function EmployeeDashboard() {
    const { user } = useAuthStore();
    return <div className="p-8 text-foreground">Employee Dashboard — Welcome {user?.full_name}</div>;
}