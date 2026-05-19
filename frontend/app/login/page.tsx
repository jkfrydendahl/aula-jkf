"use client";

import { useState, useEffect, useCallback } from "react";
import { api, AuthStatusResponse } from "@/lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [flowId, setFlowId] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const startAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const { flow_id } = await api.authStart(username);
      setFlowId(flow_id);
      setPolling(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const pollStatus = useCallback(async () => {
    if (!flowId) return;
    try {
      const result = await api.authStatus(flowId);
      setStatus(result);

      if (result.status === "complete") {
        setPolling(false);
        window.location.href = "/dashboard";
      } else if (result.status === "error") {
        setPolling(false);
        setError(result.message || "Authentication failed");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setPolling(false);
    }
  }, [flowId]);

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(pollStatus, 2000);
    return () => clearInterval(interval);
  }, [polling, pollStatus]);

  const selectIdentity = async (index: number) => {
    if (!flowId) return;
    await api.authSelectIdentity(flowId, index);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-xl shadow-lg">
        <div>
          <h1 className="text-3xl font-bold text-center text-gray-900">Aula</h1>
          <p className="mt-2 text-center text-gray-600">Log ind med MitID</p>
        </div>

        {!flowId && (
          <form onSubmit={startAuth} className="space-y-4">
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="MitID brugernavn"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
            <button
              type="submit"
              className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition"
            >
              Start login
            </button>
          </form>
        )}

        {flowId && status?.status === "pending" && (
          <div className="text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-blue-100 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
            <p className="text-gray-600">{status.message || "Godkend i MitID app..."}</p>
            {status.qr_data && (
              <div className="p-4 bg-gray-100 rounded-lg">
                <p className="text-sm text-gray-500 mb-2">Scan QR-kode:</p>
                <code className="text-xs break-all">{status.qr_data}</code>
              </div>
            )}
          </div>
        )}

        {status?.status === "awaiting_identity" && status.identities && (
          <div className="space-y-4">
            <p className="text-gray-700 font-medium">Vælg identitet:</p>
            {status.identities.map((name, idx) => (
              <button
                key={idx}
                onClick={() => selectIdentity(idx + 1)}
                className="w-full py-3 px-4 border border-gray-300 rounded-lg hover:bg-blue-50 hover:border-blue-300 transition text-left"
              >
                {name}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
