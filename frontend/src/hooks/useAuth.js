import { useState, useEffect, useCallback } from "react";

// Session auth. `user` is undefined while loading, null when signed out, or
// { email } when signed in. Cookies are same-origin (Vite proxy), so they ride
// along automatically.
export function useAuth() {
  const [user, setUser] = useState(undefined);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => (r.ok ? r.json() : null))
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  const submit = useCallback(async (kind, email, password) => {
    const r = await fetch(`/api/auth/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "something went wrong");
    setUser({ email: d.email });
    return d;
  }, []);

  const login = useCallback((e, p) => submit("login", e, p), [submit]);
  const register = useCallback((e, p) => submit("register", e, p), [submit]);
  const logout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    setUser(null);
  }, []);

  return { user, login, register, logout };
}
