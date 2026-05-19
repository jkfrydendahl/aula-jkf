"use client";

import { useState, useEffect } from "react";
import { api, Child, Presence, Message } from "@/lib/api";

export default function DashboardPage() {
  const [children, setChildren] = useState<Child[]>([]);
  const [presence, setPresence] = useState<Record<string, Presence>>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      const [childrenData, messagesData] = await Promise.all([
        api.getChildren(),
        api.getMessages(),
      ]);
      setChildren(childrenData);
      setMessages(messagesData);

      // Fetch presence for each child
      const presenceMap: Record<string, Presence> = {};
      for (const child of childrenData) {
        try {
          presenceMap[child.id] = await api.getPresence(child.id);
        } catch {
          // Skip if presence unavailable
        }
      }
      setPresence(presenceMap);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="p-6 bg-red-50 rounded-lg max-w-md">
          <p className="text-red-700">{error}</p>
          <button onClick={loadData} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg">
            Prøv igen
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <header className="max-w-4xl mx-auto mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Aula Dashboard</h1>
      </header>

      <main className="max-w-4xl mx-auto space-y-8">
        {/* Children & Presence */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Børn</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {children.map((child) => {
              const p = presence[child.id];
              return (
                <div key={child.id} className="bg-white rounded-lg shadow p-5">
                  <h3 className="font-medium text-gray-900">{child.name}</h3>
                  <p className="text-sm text-gray-500">{child.institution}</p>
                  {p && (
                    <div className="mt-3 space-y-1">
                      <StatusBadge status={p.status} />
                      {p.check_in_time && (
                        <p className="text-sm text-gray-600">
                          Kommet: {p.check_in_time}
                          {p.check_out_time && ` → Hentet: ${p.check_out_time}`}
                        </p>
                      )}
                      {p.exit_with && (
                        <p className="text-sm text-gray-600">Hentes af: {p.exit_with}</p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* Messages */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Beskeder
            {messages.filter((m) => !m.is_read).length > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded-full">
                {messages.filter((m) => !m.is_read).length} ulæste
              </span>
            )}
          </h2>
          <div className="bg-white rounded-lg shadow divide-y">
            {messages.length === 0 && (
              <p className="p-4 text-gray-500">Ingen beskeder</p>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`p-4 ${!msg.is_read ? "bg-blue-50" : ""}`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium text-gray-900">{msg.subject}</p>
                    <p className="text-sm text-gray-600">Fra: {msg.sender}</p>
                  </div>
                  <time className="text-xs text-gray-400">
                    {new Date(msg.timestamp).toLocaleDateString("da-DK")}
                  </time>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    checked_in: "bg-green-100 text-green-700",
    checked_out: "bg-gray-100 text-gray-700",
    sick: "bg-yellow-100 text-yellow-700",
    vacation: "bg-purple-100 text-purple-700",
    unknown: "bg-gray-100 text-gray-500",
  };
  const labels: Record<string, string> = {
    checked_in: "Til stede",
    checked_out: "Gået hjem",
    sick: "Syg",
    vacation: "Ferie",
    unknown: "Ukendt",
  };
  const colorClass = colors[status] || colors.unknown;
  const label = labels[status] || status;

  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${colorClass}`}>
      {label}
    </span>
  );
}
