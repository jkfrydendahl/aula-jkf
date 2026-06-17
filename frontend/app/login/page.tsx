"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api, AuthStatusResponse } from "@/lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [flowId, setFlowId] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [qrFrame, setQrFrame] = useState(false);

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
    const interval = setInterval(pollStatus, 1000);
    return () => clearInterval(interval);
  }, [polling, pollStatus]);

  // Alternate QR codes every 1 second for TQR animation
  useEffect(() => {
    if (!status?.qr_data || !status?.qr_data_2) return;
    const interval = setInterval(() => setQrFrame((f) => !f), 1000);
    return () => clearInterval(interval);
  }, [status?.qr_data, status?.qr_data_2]);

  const selectIdentity = async (index: number) => {
    if (!flowId) return;
    await api.authSelectIdentity(flowId, index);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="max-w-md w-full space-y-8 p-8 bg-white dark:bg-gray-800 rounded-xl shadow-lg dark:shadow-gray-900">
        <div>
          <h1 className="text-3xl font-bold text-center text-gray-900 dark:text-white">Aula JKF</h1>
          <p className="mt-2 text-center text-gray-600 dark:text-gray-400">Log ind med MitID</p>
        </div>

        {!flowId && (
          <form onSubmit={startAuth} className="space-y-4">
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="MitID brugernavn"
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
            {!status.qr_data && (
              <div className="w-16 h-16 mx-auto bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            )}
            <p className="text-gray-600 dark:text-gray-400">{status.message || "Godkend i MitID app..."}</p>
            {status.qr_data && (
              <div className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Scan med MitID app:</p>
                <div
                  className="mx-auto w-[250px] h-[250px] [&>svg]:w-full [&>svg]:h-full"
                  dangerouslySetInnerHTML={{
                    __html: (qrFrame && status.qr_data_2) ? status.qr_data_2 : status.qr_data
                  }}
                />
              </div>
            )}
          </div>
        )}

        {status?.status === "identity_selection" && status.identities && (
          <div className="space-y-4">
            <p className="text-gray-700 dark:text-gray-300 font-medium">Vælg identitet:</p>
            {status.identities.map((name, idx) => (
              <button
                key={idx}
                onClick={() => selectIdentity(idx + 1)}
                className="w-full py-3 px-4 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:border-blue-300 dark:hover:border-blue-700 transition text-left"
              >
                {name}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-red-700 dark:text-red-400 text-sm">{error}</p>
          </div>
        )}

        <div className="text-center pt-2">
          <button
            onClick={async () => {
              await api.appAuthLogout().catch(() => {});
              window.location.href = "/";
            }}
            className="text-sm text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition"
          >
            ← Skift bruger
          </button>
        </div>
      </div>
    </div>
  );
}
