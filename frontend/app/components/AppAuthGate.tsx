"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type AppAuthUser = {
  name: string;
};

export default function AppAuthGate({ children }: { children: React.ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [users, setUsers] = useState<AppAuthUser[]>([]);
  const [selectedUser, setSelectedUser] = useState<AppAuthUser | null>(null);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function check() {
      try {
        const [me, availableUsers] = await Promise.all([
          api.appAuthMe(),
          api.appAuthUsers(),
        ]);

        if (!active) {
          return;
        }

        setAuthenticated(me.authenticated);
        setUsers(availableUsers);
        if (availableUsers.length === 1) {
          setSelectedUser(availableUsers[0]);
        }
      } catch {
        if (active) {
          setAuthenticated(false);
          setUsers([]);
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

  const showSelector = useMemo(
    () => users.length > 1 && selectedUser === null,
    [selectedUser, users.length],
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selectedUser) {
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const result = await api.appAuthLogin(selectedUser.name, password);
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

  function onSelectUser(user: AppAuthUser) {
    setSelectedUser(user);
    setPassword("");
    setError(null);
  }

  function onBackToUserSelection() {
    setSelectedUser(null);
    setPassword("");
    setError(null);
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-gray-900">
        <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow dark:bg-gray-800 dark:shadow-gray-900">
          {showSelector ? (
            <div className="space-y-4">
              <div className="space-y-1">
                <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Vælg bruger</h1>
                <p className="text-sm text-gray-600 dark:text-gray-300">Vælg den profil du vil logge ind med.</p>
              </div>
              <div className="space-y-3">
                {users.map((user) => (
                  <button
                    key={user.name}
                    type="button"
                    onClick={() => onSelectUser(user)}
                    className="w-full rounded-xl border border-gray-200 px-4 py-3 text-left font-medium text-gray-900 transition hover:border-blue-500 hover:bg-blue-50 dark:border-gray-700 dark:text-white dark:hover:border-blue-400 dark:hover:bg-gray-700"
                  >
                    {user.name}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-1">
                <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Adgangskode</h1>
                {users.length > 1 && selectedUser ? (
                  <button
                    type="button"
                    onClick={onBackToUserSelection}
                    className="text-sm text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    ← Vælg en anden bruger
                  </button>
                ) : selectedUser?.name ? (
                  <p className="text-sm text-gray-600 dark:text-gray-300">{selectedUser.name}</p>
                ) : null}
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Adgangskode"
                className="w-full rounded-lg border border-gray-300 px-4 py-3 focus:border-transparent focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                autoFocus
                required
              />
              {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
              <button
                type="submit"
                disabled={submitting || !selectedUser}
                className="w-full rounded-lg bg-blue-600 px-4 py-3 font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "Tjekker..." : "Fortsæt"}
              </button>
            </form>
          )}
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
