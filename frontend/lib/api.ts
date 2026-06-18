const API_BASE = "/api";

type RequestOptions = RequestInit & {
  noRedirectOn401?: boolean;
};

async function request<T>(path: string, options?: RequestOptions): Promise<T> {
  const { noRedirectOn401, ...fetchOptions } = options || {};
  const res = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    },
  });

  let data: unknown = null;
  if (res.status === 401 || !res.ok) {
    try {
      data = await res.json();
    } catch {
      data = null;
    }
  }

  if (res.status === 401 && !noRedirectOn401) {
    const authError = data as { app_auth_required?: boolean; re_auth_required?: boolean; detail?: { app_auth_required?: boolean; re_auth_required?: boolean } } | null;
    if (authError?.app_auth_required || authError?.detail?.app_auth_required) {
      window.location.href = "/";
      throw new Error("App authentication required");
    }
    if (authError?.re_auth_required || authError?.detail?.re_auth_required) {
      // Don't auto-redirect — throw a typed error so the dashboard can show an inline banner
      throw Object.assign(new Error("Aula re-authentication required"), { re_auth_required: true });
    }
  }

  if (!res.ok) {
    const message =
      (data as { detail?: string } | null)?.detail ||
      `API error: ${res.status}`;
    throw new Error(message);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

export interface AuthStartResponse {
  flow_id: string;
}

export interface AuthStatusResponse {
  status: "pending" | "qr_ready" | "identity_selection" | "complete" | "error";
  message?: string;
  error?: string;
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
  attachments?: { id: string; name: string; url?: string }[];
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
  appAuthMe: () =>
    request<{ authenticated: boolean; username?: string }>("/app-auth/me", { noRedirectOn401: true }),

  appAuthUsers: () =>
    request<{ name: string }[]>("/app-auth/users", { noRedirectOn401: true }),

  appAuthLogin: (username: string, password: string) =>
    request<{ authenticated: boolean }>("/app-auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      noRedirectOn401: true,
    }),

  appAuthLogout: () =>
    request<{ authenticated: boolean }>("/app-auth/logout", {
      method: "POST",
      noRedirectOn401: true,
    }),

  authStart: (username: string) =>
    request<AuthStartResponse>("/auth/start", {
      method: "POST",
      body: JSON.stringify({ username }),
    }),

  authStatus: (flowId: string) =>
    request<AuthStatusResponse>(`/auth/status/${flowId}`),

  authSelectIdentity: (flowId: string, identityIndex: number) =>
    request<void>(`/auth/select-identity/${flowId}`, {
      method: "POST",
      body: JSON.stringify({ identity_index: identityIndex }),
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
  markUnread: (threadId: string) => request<{ success: boolean }>(`/messages/${threadId}/unread`, { method: "POST" }),
  getPosts: () => request<Post[]>("/posts"),
  markPostRead: (postId: string) => request<{ success: boolean }>(`/posts/${postId}/read`, { method: "POST" }),
  markPostUnread: (postId: string) => request<{ success: boolean }>(`/posts/${postId}/unread`, { method: "POST" }),
  getVacationRegistrations: () => request<VacationRegistration[]>("/vacation-registrations"),
  getVacationResponse: (responseId: number) => request<{ days: { date: string; isComing: boolean }[] }>(`/vacation-registrations/${responseId}`),
  submitVacationResponse: (responseId: number, childId: number, days: { date: string; isComing: boolean; entryTime: string; exitTime: string }[], comment?: string) =>
    request<{ success: boolean; error?: string }>("/vacation-registrations/respond", {
      method: "POST",
      body: JSON.stringify({ response_id: responseId, child_id: childId, days, comment }),
    }),
  getCalendar: (childId: string) => request<CalendarEvent[]>(`/calendar/${childId}`),

  // Push notifications
  pushSubscribe: (subscription: PushSubscriptionJSON) =>
    request<{ status: string }>("/push/subscribe", {
      method: "POST",
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        keys: subscription.keys,
      }),
    }),
  pushUnsubscribe: (endpoint: string) =>
    request<{ status: string }>("/push/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ endpoint }),
    }),

  // Actions
  sendMessage: (recipientId: string, subject: string, text: string) =>
    request<{ success: boolean }>("/messages/send", {
      method: "POST",
      body: JSON.stringify({ recipient_id: recipientId, subject, text }),
    }),
};
