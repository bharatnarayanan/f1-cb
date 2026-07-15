import { useState } from "react";
import { login } from "../api/client";
import { setToken } from "../api/auth";

export function Login({ onLoginSuccess }: { onLoginSuccess: () => void }) {
  const [email, setEmail] = useState("founder@local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await login(email, password);
      setToken(result.access_token);
      onLoginSuccess();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
      <form onSubmit={handleSubmit} className="card" style={{ width: 320 }}>
        <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 16 }}>TIP — Sign in</div>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ width: "100%", marginBottom: 8, padding: 6, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{ width: "100%", marginBottom: 8, padding: 6, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 }}
        />
        <button className="btn" type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Signing in..." : "Sign in"}
        </button>
        {error && <div className="empty-state bearish" style={{ marginTop: 8 }}>{error}</div>}
      </form>
    </div>
  );
}
