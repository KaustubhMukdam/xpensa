import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "@/lib/axios";
import { useAuthStore } from "@/store/auth";
import type { AuthUser } from "@/store/auth";

interface Country {
  name: { common: string };
  currencies?: Record<string, { name: string; symbol: string }>;
  cca2: string;
  flag: string;
}

interface CountryOption {
  name: string;
  currency: string;
  currencyName: string;
  flag: string;
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [companyName, setCompanyName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [country, setCountry] = useState("");
  const [baseCurrency, setBaseCurrency] = useState("");
  const [currencyLabel, setCurrencyLabel] = useState("");

  const [countries, setCountries] = useState<CountryOption[]>([]);
  const [loadingCountries, setLoadingCountries] = useState(true);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Fetch country list with currencies
  useEffect(() => {
    fetch("https://restcountries.com/v3.1/all?fields=name,currencies,cca2,flag")
      .then((r) => r.json())
      .then((data: Country[]) => {
        const options: CountryOption[] = data
          .filter((c) => c.currencies)
          .map((c) => {
            const currCodes = Object.keys(c.currencies!);
            const currCode = currCodes[0] ?? "USD";
            const currInfo = c.currencies![currCode];
            return {
              name: c.name.common,
              currency: currCode,
              currencyName: currInfo?.name ?? "",
              flag: c.flag,
            };
          })
          .sort((a, b) => a.name.localeCompare(b.name));
        setCountries(options);
      })
      .catch(() => {
        // Fallback if fetch fails
        setCountries([
          { name: "India", currency: "INR", currencyName: "Indian Rupee", flag: "🇮🇳" },
          { name: "United States", currency: "USD", currencyName: "US Dollar", flag: "🇺🇸" },
          { name: "United Kingdom", currency: "GBP", currencyName: "Pound Sterling", flag: "🇬🇧" },
          { name: "European Union", currency: "EUR", currencyName: "Euro", flag: "🇪🇺" },
        ]);
      })
      .finally(() => setLoadingCountries(false));
  }, []);

  const handleCountryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = countries.find((c) => c.name === e.target.value);
    setCountry(e.target.value);
    if (selected) {
      setBaseCurrency(selected.currency);
      setCurrencyLabel(`${selected.flag} ${selected.currency} — ${selected.currencyName}`);
    } else {
      setBaseCurrency("");
      setCurrencyLabel("");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!baseCurrency) {
      setError("Please select a country to determine the base currency.");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/api/v1/auth/register", {
        company_name: companyName,
        full_name: fullName,
        email,
        password,
        country,
        base_currency: baseCurrency,
      });
      setAuth(data.access_token, data.user as AuthUser);
      navigate("/admin");
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="orb orb-1" />
      <div className="orb orb-2" />

      <div className="auth-card auth-card-wide">
        <div className="auth-logo">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="8" fill="url(#logoGrad2)" />
            <path d="M8 20L14 12L19 17L23 11" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="23" cy="11" r="2" fill="white" />
            <defs>
              <linearGradient id="logoGrad2" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                <stop stopColor="#10b981" />
                <stop offset="1" stopColor="#059669" />
              </linearGradient>
            </defs>
          </svg>
          <span className="auth-logo-text">xpensa</span>
        </div>

        <div className="auth-header">
          <h1 className="auth-title">Create your workspace</h1>
          <p className="auth-subtitle">Set up your company and admin account</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="companyName" className="form-label">Company name</label>
              <input
                id="companyName"
                type="text"
                className="form-input"
                placeholder="Acme Corp"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="fullName" className="form-label">Your full name</label>
              <input
                id="fullName"
                type="text"
                className="form-input"
                placeholder="Jane Smith"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="reg-email" className="form-label">Work email</label>
            <input
              id="reg-email"
              type="email"
              className="form-input"
              placeholder="jane@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="reg-password" className="form-label">Password</label>
            <div className="input-with-icon">
              <input
                id="reg-password"
                type={showPassword ? "text" : "password"}
                className="form-input"
                placeholder="Min. 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
              <button
                type="button"
                className="input-icon-btn"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="country" className="form-label">Country</label>
              <select
                id="country"
                className="form-input form-select"
                value={country}
                onChange={handleCountryChange}
                required
                disabled={loadingCountries}
              >
                <option value="">{loadingCountries ? "Loading countries…" : "Select country"}</option>
                {countries.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.flag} {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Base currency</label>
              <div className={`currency-badge ${baseCurrency ? "currency-badge-active" : ""}`}>
                {currencyLabel || "Auto-detected from country"}
              </div>
            </div>
          </div>

          {error && (
            <div className="form-error" role="alert">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
              {error}
            </div>
          )}

          <button type="submit" className="btn-primary" disabled={loading || loadingCountries}>
            {loading ? (
              <span className="btn-loading">
                <svg className="spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" opacity=".25" />
                  <path d="M21 12a9 9 0 00-9-9" />
                </svg>
                Creating workspace…
              </span>
            ) : "Create workspace"}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{" "}
          <Link to="/login" className="auth-link">Sign in</Link>
        </p>
      </div>
    </div>
  );
}