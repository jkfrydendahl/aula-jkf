const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (res.status === 401) {
    const data = await res.json();
    if (data.re_auth_required) {
      window.location.href = "/login";
      throw new Error("Authentication required");
    }
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

export interface AuthStartResponse {
  flow_id: string;
}

export interface AuthStatusResponse {
  status: "pending" | "awaiting_identity" | "complete" | "error";
  message?: string;
  qr_data?: string;
  qr_data_2?: string;
  identities?: string[];
}

export interface Child {
  id: string;
  name: string;
  institution: string;
}

export interface Presence {
  child_id: string;
  status: string;
  check_in_time?: string;
  check_out_time?: string;
  exit_with?: string;
  comment?: string;
}

export interface Message {
  id: string;
  subject: string;
  sender: string;
  timestamp: string;
  is_read: boolean;
  text?: string;
}

export interface CalendarEvent {
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  description?: string;
}

// Auth
export const api = {
  authStart: (username: string) =>
    request<AuthStartResponse>("/auth/start", {
      method: "POST",
      body: JSON.stringify({ username }),
    }),

  authStatus: (flowId: string) =>
    request<AuthStatusResponse>(`/auth/status/${flowId}`),

  authSelectIdentity: (flowId: string, identity: number) =>
    request<void>(`/auth/select-identity/${flowId}`, {
      method: "POST",
      body: JSON.stringify({ identity }),
    }),

  // Data
  getChildren: () => request<Child[]>("/children"),
  getPresence: (childId: string) => request<Presence>(`/presence/${childId}`),
  getMessages: () => request<Message[]>("/messages"),
  getCalendar: (childId: string) => request<CalendarEvent[]>(`/calendar/${childId}`),

  // Actions
  sendMessage: (recipientId: string, subject: string, text: string) =>
    request<{ success: boolean }>("/messages/send", {
      method: "POST",
      body: JSON.stringify({ recipient_id: recipientId, subject, text }),
    }),
};
