"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function AppAuthGate({ children }: { children: React.ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function check() {
      try {
        const result = await api.appAuthMe();
        if (active) {
          setAuthenticated(result.authenticated);
        }
      } catch {
        if (active) {
          setAuthenticated(false);
        }
      } finally {
        if (active) {
          setChecking(false);
        }
      }
    }

    check();

    return () => {
      active = false;
    };
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const result = await api.appAuthLogin(password);
      if (result.authenticated) {
        setAuthenticated(true);
        setPassword("");
        return;
      }
      setError("Forkert adgangskode");
    } catch {
      setError("Forkert adgangskode");
    } finally {
      setSubmitting(false);
    }
  }

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
        <form
          onSubmit={onSubmit}
          className="w-full max-w-sm bg-white dark:bg-gray-800 rounded-xl shadow dark:shadow-gray-900 p-6 space-y-4"
        >
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Adgangskode kræves</h1>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Adgangskode"
            className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            autoFocus
            required
          />
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition disabled:opacity-50"
          >
            {submitting ? "Tjekker..." : "Fortsæt"}
          </button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
