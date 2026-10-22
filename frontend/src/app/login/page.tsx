"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { setAuthToken } from "@/lib/api";
import { useGreenlineAuth } from "@/components/AuthProvider";
import { TrendingUp, Lock, User, ShieldCheck } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const { isAuth0Enabled, isAuthenticated, loginWithAuth0 } = useGreenlineAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPasswordLogin, setShowPasswordLogin] = useState(!isAuth0Enabled);

  useEffect(() => {
    document.title = "Login · greenline";
    if (isAuthenticated) {
      router.push("/");
    }
  }, [isAuthenticated, router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const formData = new URLSearchParams();
      formData.append("username", username);
      formData.append("password", password);

      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData.toString(),
      });

      if (!res.ok) {
        throw new Error("Invalid username or password");
      }

      const data = await res.json();
      setAuthToken(data.access_token);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Failed to log in");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4 w-full">
      <div className="bg-white rounded-3xl border border-slate-200/80 p-8 md:p-10 max-w-md w-full shadow-[0_20px_50px_rgba(0,0,0,0.06)] relative">
        <div className="text-center mb-8">
          <div className="inline-flex p-3 bg-[#9FE837] text-[#0F172A] rounded-2xl shadow-[0_4px_16px_rgba(159,232,55,0.4)] mb-4">
            <TrendingUp className="w-8 h-8 stroke-[2.5]" />
          </div>
          <h1 className="text-2xl font-extrabold text-[#0F172A] tracking-tight">Welcome to Greenline</h1>
          <p className="text-xs font-semibold text-slate-500 mt-1">Sign in to your personal investment tracker</p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-600 text-xs font-bold rounded-2xl text-center">
            {error}
          </div>
        )}

        {isAuth0Enabled && (
          <div className="mb-6 space-y-4">
            <button
              type="button"
              onClick={() => loginWithAuth0()}
              className="w-full flex items-center justify-center gap-3 py-3.5 bg-[#635BFF] hover:bg-[#5248E5] text-white font-bold text-sm rounded-2xl shadow-md transition-all active:scale-[0.98]"
            >
              <ShieldCheck className="w-5 h-5" />
              <span>Continue with Auth0</span>
            </button>

            <div className="relative flex items-center justify-center py-2">
              <div className="border-t border-slate-200 w-full" />
              <button
                type="button"
                onClick={() => setShowPasswordLogin(!showPasswordLogin)}
                className="bg-white px-3 text-[11px] font-bold text-slate-400 hover:text-slate-600 uppercase tracking-wider relative whitespace-nowrap"
              >
                {showPasswordLogin ? "Hide Password Login" : "Or use password"}
              </button>
            </div>
          </div>
        )}

        {(!isAuth0Enabled || showPasswordLogin) && (
          <form onSubmit={handleLogin} className="space-y-4 text-sm">
            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1">Username</label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 text-slate-900 font-semibold rounded-2xl pl-10 pr-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#9FE837]"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 text-slate-900 font-semibold rounded-2xl pl-10 pr-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#9FE837]"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 bg-[#0F172A] hover:bg-slate-800 font-extrabold text-white text-xs uppercase tracking-wider rounded-full shadow-md transition-all btn-press mt-2 disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign In with Password"}
            </button>
          </form>
        )}

        <p className="text-center text-xs font-semibold text-slate-400 mt-6 pt-4 border-t border-slate-100">
          Default seed credentials: <code className="text-slate-700 font-mono bg-slate-100 px-1.5 py-0.5 rounded-md">admin</code> / <code className="text-slate-700 font-mono bg-slate-100 px-1.5 py-0.5 rounded-md">admin123</code>
        </p>
      </div>
    </div>
  );
}
