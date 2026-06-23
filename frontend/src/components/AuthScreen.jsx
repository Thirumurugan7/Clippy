import { useState } from "react";

// Sign in / create account. Single screen with a mode toggle.
export function AuthScreen({ onLogin, onRegister }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await (mode === "login" ? onLogin : onRegister)(email, password);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={submit}>
        <img src="/clippy-logo.png" alt="Clippy" className="auth-logo" />
        <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p className="auth-sub">Turn long videos into shorts — privately, on your own machine.</p>
        <input
          type="email" placeholder="you@example.com" value={email} autoComplete="email"
          onChange={(e) => setEmail(e.target.value)} required
        />
        <input
          type="password" placeholder="Password (6+ characters)" value={password}
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          onChange={(e) => setPassword(e.target.value)} required
        />
        {error && <p className="error auth-error">{error}</p>}
        <button className="btn-amber full" type="submit" disabled={busy}>
          {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <button
          type="button" className="auth-toggle"
          onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
        >
          {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
