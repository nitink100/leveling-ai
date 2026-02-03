"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { loginAdmin } from "@/lib/api";
import { setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const data = await loginAdmin({ username: username.trim(), password });
      setToken(data.access_token);
      router.push("/");
    } catch (e: any) {
      setErr(e?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container" style={{ maxWidth: 520 }}>
      <div className="title">Admin Login</div>
      <div className="subtitle">Use the credentials shared by the interviewer.</div>

      <div style={{ marginTop: 18 }} className="card">
        <div className="cardBody">
          <form onSubmit={onSubmit} style={{ display: "grid", gap: 12 }}>
            <div className="field">
              <label className="label">Username</label>
              <input
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                autoComplete="username"
                required
              />
            </div>

            <div className="field">
              <label className="label">Password</label>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
              />
            </div>

            <button className={`btn btnPrimary`} disabled={loading} type="submit">
              {loading ? "Signing in…" : "Sign in"}
            </button>

            {err ? <div className="errorBox">{err}</div> : null}
          </form>
        </div>
      </div>
    </main>
  );
}
