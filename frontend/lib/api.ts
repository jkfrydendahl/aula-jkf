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
  profile_id: string;
  name: string;
  institution: string;
}

export interface Presence {
  child_id: string;
  status: string;
  planned_start?: string;
  planned_end?: string;
  check_in_time?: string;
  check_out_time?: string;
  exit_with?: string;
  location?: string;
  comment?: string;
}

export interface PickupResponsible {
  id: string;
  name: string;
  relation: string;
}

export interface GoHomeWithChild {
  id: string;
  name: string;
  group: string;
}

export interface Message {
  id: string;
  subject: string;
  sender: string;
  timestamp: string;
  is_read: boolean;
  preview?: string;
  text?: string;
  child_profile_ids?: string[];
  recipients?: string[];
}

export interface ThreadDetail {
  subject: string;
  messages: {
    id: string;
    sender: string;
    timestamp: string;
    text: string;
    attachments?: {
      id: number;
      name: string;
      url: string;
    }[];
  }[];
}

export interface CalendarEvent {
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  description?: string;
}

export interface Post {
  id: string;
  title: string;
  content: string;
  sender: string;
  institution: string;
  timestamp: string;
  is_important: boolean;
  is_read: boolean;
  allow_comments: boolean;
  comment_count: number;
  child_profile_ids?: string[];
  attachments: {
    id: number;
    name: string;
    url: string;
  }[];
}

export interface VacationRegistration {
  id: number;
  response_id: number;
  title: string;
  note: string;
  start_date: string;
  end_date: string;
  deadline: string;
  is_editable: boolean;
  is_missing_answer: boolean;
  child_name: string;
  child_id: string;
  child_profile_id: string;
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

  authCheck: () =>
    request<{ authenticated: boolean; reason?: string }>("/auth/check"),

  // Data
  getChildren: () => request<Child[]>("/children"),
  getPresence: (childId: string) => request<Presence>(`/presence/${childId}`),
  updatePresence: (childId: string, status: string) =>
    request<{ success: boolean }>("/presence/update", {
      method: "POST",
      body: JSON.stringify({ child_id: childId, status }),
    }),
  updateSickStatus: (childId: string, isSick: boolean) =>
    request<{ success: boolean }>("/presence/sick", {
      method: "POST",
      body: JSON.stringify({ child_id: childId, is_sick: isSick }),
    }),
  getPickupResponsibles: (childId: string) =>
    request<PickupResponsible[]>(`/presence/${childId}/pickup-responsibles`),
  getGoHomeWithList: (childId: string) =>
    request<GoHomeWithChild[]>(`/presence/${childId}/go-home-with-list`),
  updatePresenceTemplate: (data: {
    child_id: string;
    date: string;
    activity_type: number;
    entry_time: string;
    exit_time: string;
    exit_with?: string;
    comment?: string;
  }) =>
    request<{ success: boolean }>("/presence/update-template", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getMessages: () => request<Message[]>("/messages"),
  getThread: (threadId: string) => request<ThreadDetail>(`/messages/${threadId}`),
  markRead: (threadId: string) => request<{ success: boolean }>(`/messages/${threadId}/read`, { method: "POST" }),
  getPosts: () => request<Post[]>("/posts"),
  getVacationRegistrations: () => request<VacationRegistration[]>("/vacation-registrations"),
  getVacationResponse: (responseId: number) => request<{ days: { date: string; isComing: boolean }[] }>(`/vacation-registrations/${responseId}`),
  submitVacationResponse: (responseId: number, childId: number, days: { date: string; isComing: boolean; entryTime: string; exitTime: string }[], comment?: string) =>
    request<{ success: boolean; error?: string }>("/vacation-registrations/respond", {
      method: "POST",
      body: JSON.stringify({ response_id: responseId, child_id: childId, days, comment }),
    }),
  getCalendar: (childId: string) => request<CalendarEvent[]>(`/calendar/${childId}`),

  // Actions
  sendMessage: (recipientId: string, subject: string, text: string) =>
    request<{ success: boolean }>("/messages/send", {
      method: "POST",
      body: JSON.stringify({ recipient_id: recipientId, subject, text }),
    }),
};
