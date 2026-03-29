export default function NotFound() {
    return (
        <div className="flex min-h-screen items-center justify-center">
            <div className="text-center">
                <h1 className="text-4xl font-bold text-foreground">404</h1>
                <p className="mt-2 text-muted-foreground">Page not found</p>
                <a href="/login" className="mt-4 inline-block text-primary underline">Go to Login</a>
            </div>
        </div>
    );
}