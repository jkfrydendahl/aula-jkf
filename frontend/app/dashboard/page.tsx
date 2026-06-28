"use client";

import { useState, useEffect, useRef } from "react";
import DOMPurify from "dompurify";
import { api, Child, Presence, PickupResponsible, GoHomeWithChild, Message, ThreadDetail, Post, VacationRegistration } from "@/lib/api";

const OFFICE_EXTENSIONS = ["doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp"];

function getAttachmentHref(url: string, name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (OFFICE_EXTENSIONS.includes(ext)) {
    return `https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(url)}`;
  }
  return url;
}

// Toast notification type
interface Toast {
  id: number;
  message: string;
  type: "success" | "error";
}

export default function DashboardPage() {
  const [children, setChildren] = useState<Child[]>([]);
  const [presence, setPresence] = useState<Record<string, Presence>>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [vacations, setVacations] = useState<VacationRegistration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authNeeded, setAuthNeeded] = useState(false);
  const [selectedThread, setSelectedThread] = useState<ThreadDetail | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);
  const [childFilter, setChildFilter] = useState<string>("all");
  const [activeTab, setActiveTab] = useState<"messages" | "posts" | "vacation">("messages");
  const [selectedPost, setSelectedPost] = useState<Post | null>(null);
  const [selectedVacation, setSelectedVacation] = useState<VacationRegistration | null>(null);
  const [vacationDays, setVacationDays] = useState<{ date: string; isComing: boolean }[]>([]);
  const [vacationSubmitting, setVacationSubmitting] = useState(false);
  const listScrollPos = useRef<number>(0);

  // Pickup form state
  const [pickupFormChild, setPickupFormChild] = useState<string | null>(null);
  const [pickupResponsibles, setPickupResponsibles] = useState<PickupResponsible[]>([]);
  const [goHomeWithList, setGoHomeWithList] = useState<GoHomeWithChild[]>([]);
  const [pickupType, setPickupType] = useState<number>(0);
  const [pickupExitTime, setPickupExitTime] = useState("15:00");
  const [pickupExitWith, setPickupExitWith] = useState("");
  const [pickupSubmitting, setPickupSubmitting] = useState(false);

  // Toast notifications
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);

  function showToast(message: string, type: "success" | "error" = "success") {
    const id = ++toastIdRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }

  async function fetchPresenceMap(childrenData: Child[]) {
    const presenceResults = await Promise.all(
      childrenData.map((child) => api.getPresence(child.id).catch(() => null))
    );
    const presenceMap: Record<string, Presence> = {};
    childrenData.forEach((child, index) => {
      const result = presenceResults[index];
      if (result) {
        presenceMap[child.id] = result;
      }
    });
    return presenceMap;
  }

  useEffect(() => {
    loadData();
  }, []);

  // Auto-refresh presence every 60 seconds, messages/posts every 5 minutes
  // Pauses when tab is not visible (saves battery/bandwidth on mobile)
  useEffect(() => {
    if (children.length === 0) return;

    let presenceInterval: ReturnType<typeof setInterval>;
    let contentInterval: ReturnType<typeof setInterval>;

    function startIntervals() {
      presenceInterval = setInterval(async () => {
        if (document.hidden) return;
        try {
          setPresence(await fetchPresenceMap(children));
        } catch { /* silent refresh failure */ }
      }, 60000);

      contentInterval = setInterval(async () => {
        if (document.hidden) return;
        try {
          const [messagesData, postsData] = await Promise.all([
            api.getMessages(),
            api.getPosts(),
          ]);
          setMessages(messagesData);
          setPosts(postsData);
        } catch { /* silent refresh failure */ }
      }, 300000);
    }

    // Refresh immediately when tab becomes visible again
    function handleVisibilityChange() {
      if (!document.hidden) {
        (async () => {
          try {
            setPresence(await fetchPresenceMap(children));
          } catch { /* ignore */ }
          try {
            const [messagesData, postsData] = await Promise.all([
              api.getMessages(),
              api.getPosts(),
            ]);
            setMessages(messagesData);
            setPosts(postsData);
          } catch { /* ignore */ }
        })();
      }
    }

    startIntervals();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      clearInterval(presenceInterval);
      clearInterval(contentInterval);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [children]);

  // Restore scroll position when returning from detail view to list
  useEffect(() => {
    if (!selectedThread && !selectedPost) {
      const pos = listScrollPos.current;
      if (pos > 0) {
        requestAnimationFrame(() => window.scrollTo(0, pos));
      }
    }
  }, [selectedThread, selectedPost]);

  async function loadData() {
    try {
      setLoading(true);

      // Check if backend has valid tokens
      try {
        const authStatus = await api.authCheck();
        if (!authStatus.authenticated) {
          setAuthNeeded(true);
          setLoading(false);
          return;
        }
      } catch {
        // If auth check fails, try loading data anyway
      }

      const [childrenData, messagesData, postsData, vacationsData] = await Promise.all([
        api.getChildren(),
        api.getMessages(),
        api.getPosts(),
        api.getVacationRegistrations(),
      ]);
      setChildren(childrenData);
      setMessages(messagesData);
      setPosts(postsData);
      setVacations(vacationsData);

      setPresence(await fetchPresenceMap(childrenData));
    } catch (err: unknown) {
      if (err instanceof Error && (err as Error & { re_auth_required?: boolean }).re_auth_required) {
        setAuthNeeded(true);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load data");
      }
    } finally {
      setLoading(false);
    }
  }

  async function openThread(msg: Message) {
    listScrollPos.current = window.scrollY;
    setThreadLoading(true);
    try {
      const detail = await api.getThread(msg.id);
      setSelectedThread(detail);
      // Auto-mark as read when opening
      if (!msg.is_read) {
        setMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, is_read: true } : m)));
        api.markRead(msg.id).catch(() => {
          // Revert optimistic update if mark-as-read fails
          setMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, is_read: false } : m)));
        });
      }
    } catch (err) {
      console.error("Failed to load thread:", err);
      showToast("Kunne ikke åbne beskeden", "error");
    } finally {
      setThreadLoading(false);
    }
  }

  async function toggleReadStatus(msg: Message) {
    const newRead = !msg.is_read;
    setMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, is_read: newRead } : m)));
    try {
      const result = newRead ? await api.markRead(msg.id) : await api.markUnread(msg.id);
      if (!result.success) {
        setMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, is_read: !newRead } : m)));
        showToast("Kunne ikke opdatere besked", "error");
      }
    } catch {
      // Revert on network/server error
      setMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, is_read: !newRead } : m)));
      showToast("Kunne ikke opdatere besked", "error");
    }
  }

  async function togglePostReadStatus(post: Post) {
    const newRead = !post.is_read;
    setPosts((prev) => prev.map((p) => (p.id === post.id ? { ...p, is_read: newRead } : p)));
    try {
      const result = newRead ? await api.markPostRead(post.id) : await api.markPostUnread(post.id);
      if (!result.success) {
        setPosts((prev) => prev.map((p) => (p.id === post.id ? { ...p, is_read: !newRead } : p)));
        showToast("Kunne ikke opdatere opslag", "error");
      }
    } catch {
      setPosts((prev) => prev.map((p) => (p.id === post.id ? { ...p, is_read: !newRead } : p)));
      showToast("Kunne ikke opdatere opslag", "error");
    }
  }

  async function markAllPostsRead() {
    const unread = posts.filter((p) => !p.is_read);
    if (unread.length === 0) return;
    setPosts((prev) => prev.map((p) => ({ ...p, is_read: true })));
    const results = await Promise.allSettled(unread.map((p) => api.markPostRead(p.id)));
    const failedIds = unread.filter((_, i) => results[i].status === "rejected" || (results[i] as PromiseFulfilledResult<{ success: boolean }>).value?.success === false).map((p) => p.id);
    if (failedIds.length > 0) {
      setPosts((prev) => prev.map((p) => failedIds.includes(p.id) ? { ...p, is_read: false } : p));
      showToast("Kunne ikke markere alle opslag som læst", "error");
    }
  }

  async function openVacation(vac: VacationRegistration) {
    setSelectedVacation(vac);
    // Generate weekdays between start and end
    const days: { date: string; isComing: boolean }[] = [];
    const start = new Date(vac.start_date);
    const end = new Date(vac.end_date);
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const dayOfWeek = d.getDay();
      if (dayOfWeek === 0 || dayOfWeek === 6) continue;
      days.push({ date: `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`, isComing: true });
    }
    setVacationDays(days);

    // Fetch existing response to show saved state
    try {
      const response = await api.getVacationResponse(vac.response_id);
      if (response.days && response.days.length > 0) {
        const savedMap = new Map(response.days.map((d: { date: string; isComing: boolean }) => [d.date.split("T")[0], d.isComing]));
        setVacationDays((prev) =>
          prev.map((d) => ({
            ...d,
            isComing: savedMap.has(d.date) ? (savedMap.get(d.date) ?? true) : d.isComing,
          }))
        );
      }
    } catch {
      // Use defaults if fetch fails
    }
  }

  async function submitVacation() {
    if (!selectedVacation) return;
    setVacationSubmitting(true);
    try {
      const childPresence = presence[selectedVacation.child_id];
      const entryTime = childPresence?.planned_start?.slice(0, 5) || "07:30";
      const exitTime = childPresence?.planned_end?.slice(0, 5) || "16:30";
      const payload = vacationDays.map((d) => ({
        date: d.date,
        isComing: d.isComing,
        entryTime: d.isComing ? entryTime : "",
        exitTime: d.isComing ? exitTime : "",
      }));
      const result = await api.submitVacationResponse(
        selectedVacation.response_id,
        parseInt(selectedVacation.child_id),
        payload
      );
      if (result.success) {
        setVacations((prev) =>
          prev.map((v) =>
            v.response_id === selectedVacation.response_id
              ? { ...v, is_missing_answer: false }
              : v
          )
        );
        setSelectedVacation(null);
      } else {
        showToast("Kunne ikke sende feriesvar", "error");
      }
    } catch (err) {
      showToast("Kunne ikke sende feriesvar", "error");
    } finally {
      setVacationSubmitting(false);
    }
  }

  async function updatePresence(childId: string, status: string) {
    // Optimistic UI update
    setPresence((prev) => ({
      ...prev,
      [childId]: { ...prev[childId], status },
    }));
    try {
      const result = await api.updatePresence(childId, status);
      if (result.success) {
        showToast("Status opdateret");
      } else {
        showToast("Kunne ikke opdatere status", "error");
        const p = await api.getPresence(childId);
        setPresence((prev) => ({ ...prev, [childId]: p }));
      }
    } catch {
      showToast("Kunne ikke opdatere status", "error");
      // Revert on failure — reload presence
      try {
        const p = await api.getPresence(childId);
        setPresence((prev) => ({ ...prev, [childId]: p }));
      } catch { /* ignore */ }
    }
  }

  async function markSick(childId: string, isSick: boolean) {
    setPresence((prev) => ({
      ...prev,
      [childId]: { ...prev[childId], status: isSick ? "sick" : "planned" },
    }));
    try {
      const result = await api.updateSickStatus(childId, isSick);
      if (result.success) {
        showToast(isSick ? "Meldt syg" : "Sygemelding fjernet");
      } else {
        showToast("Kunne ikke opdatere sygestatus", "error");
      }
      // Refresh presence to get accurate state
      const p = await api.getPresence(childId);
      setPresence((prev) => ({ ...prev, [childId]: p }));
    } catch {
      showToast("Kunne ikke opdatere sygestatus", "error");
      try {
        const p = await api.getPresence(childId);
        setPresence((prev) => ({ ...prev, [childId]: p }));
      } catch { /* ignore */ }
    }
  }

  async function openPickupForm(childId: string) {
    setPickupFormChild(childId);
    setPickupType(0);
    setPickupExitTime(presence[childId]?.planned_end?.slice(0, 5) || "15:00");
    setPickupExitWith("");
    try {
      const [responsibles, goHomeWith] = await Promise.all([
        api.getPickupResponsibles(childId),
        api.getGoHomeWithList(childId),
      ]);
      setPickupResponsibles(responsibles);
      setGoHomeWithList(goHomeWith);
      if (responsibles.length > 0) {
        setPickupExitWith(`${responsibles[0].name} (${responsibles[0].relation})`);
      }
    } catch {
      setPickupResponsibles([]);
      setGoHomeWithList([]);
    }
  }

  async function submitPickup() {
    if (!pickupFormChild) return;
    setPickupSubmitting(true);
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
    const entryTime = presence[pickupFormChild]?.planned_start?.slice(0, 5) || "06:30";
    try {
      const result = await api.updatePresenceTemplate({
        child_id: pickupFormChild,
        date: today,
        activity_type: pickupType,
        entry_time: entryTime,
        exit_time: pickupExitTime,
        exit_with: pickupType === 0 || pickupType === 3 ? pickupExitWith : undefined,
      });
      if (!result.success) {
        showToast("Fejl ved opdatering af hentetype", "error");
      } else {
        // Refresh presence data
        const p = await api.getPresence(pickupFormChild);
        setPresence((prev) => ({ ...prev, [pickupFormChild!]: p }));
        setPickupFormChild(null);
        showToast("Hentetype opdateret");
      }
    } catch (e) {
      showToast("Fejl ved opdatering af hentetype", "error");
    } finally {
      setPickupSubmitting(false);
    }
  }

  async function logoutAppAuth() {
    try {
      await api.appAuthLogout();
    } finally {
      window.location.href = "/";
    }
  }

  async function enableNotifications() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      showToast("Push notifikationer understøttes ikke i denne browser", "error");
      return;
    }
    if (Notification.permission === "denied") {
      // On iOS PWA: Settings → Aula JKF → Notifications
      // On desktop: click the lock icon in the address bar
      showToast("Notifikationer er blokeret — aktiver dem i Indstillinger → Aula JKF → Notifikationer", "error");
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      showToast("Notifikationer blev ikke tilladt", "error");
      return;
    }
    try {
      const reg = await navigator.serviceWorker.ready;
      const vapidKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY!;
      // Safari/Apple requires applicationServerKey as Uint8Array, not a raw string
      const padding = "=".repeat((4 - (vapidKey.length % 4)) % 4);
      const base64 = (vapidKey + padding).replace(/-/g, "+").replace(/_/g, "/");
      const rawData = atob(base64);
      const applicationServerKey = new Uint8Array(rawData.length);
      for (let i = 0; i < rawData.length; i++) {
        applicationServerKey[i] = rawData.charCodeAt(i);
      }
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey,
      });
      await api.pushSubscribe(sub.toJSON() as PushSubscriptionJSON);
      showToast("Notifikationer aktiveret ✓");
    } catch {
      showToast("Kunne ikke aktivere notifikationer", "error");
    }
  }

  const notifPermission = typeof Notification !== "undefined" ? Notification.permission : "default";

  const filteredMessages = childFilter === "all"
    ? messages
    : messages.filter((msg) =>
        msg.child_profile_ids?.includes(childFilter)
      );

  const filteredPosts = childFilter === "all"
    ? posts
    : posts.filter((post) =>
        post.child_profile_ids?.includes(childFilter)
      );

  const filteredVacations = childFilter === "all"
    ? vacations
    : vacations.filter((vac) => vac.child_profile_id === childFilter);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (authNeeded) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="max-w-md w-full p-8 bg-white dark:bg-gray-800 rounded-xl shadow-lg dark:shadow-gray-900 text-center space-y-4">
          <div className="w-16 h-16 mx-auto bg-yellow-100 dark:bg-yellow-900/30 rounded-full flex items-center justify-center">
            <svg className="w-8 h-8 text-yellow-600 dark:text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">Login påkrævet</h2>
          <p className="text-gray-600 dark:text-gray-400">
            Din session er udløbet. Log ind igen med MitID for at forny adgangen.
          </p>
          <a
            href="/login"
            className="inline-block w-full py-3 px-4 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition"
          >
            Log ind med MitID
          </a>
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
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="p-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg max-w-md">
          <p className="text-red-700 dark:text-red-400">{error}</p>
          <button onClick={loadData} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg">
            Prøv igen
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <header className="max-w-4xl mx-auto mb-8">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Aula Dashboard</h1>
          <div className="flex items-center gap-4">
            <button
              onClick={enableNotifications}
              title={notifPermission === "granted" ? "Notifikationer aktiveret" : notifPermission === "denied" ? "Notifikationer blokeret — se Indstillinger" : "Aktiver notifikationer"}
              className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
            >
              {notifPermission === "granted" ? "🔔" : notifPermission === "denied" ? "🔕" : "🔔"}
            </button>
            <button
              onClick={logoutAppAuth}
              className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 underline underline-offset-2"
            >
              LOG UD
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto space-y-8">
        {/* Children & Presence */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-4">Børn</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {children.map((child) => {
              const p = presence[child.id];
              return (
                <div key={child.id} className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900 p-5">
                  <h3 className="font-medium text-gray-900 dark:text-white">{child.name}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{child.institution}</p>
                  {p && (
                    <div className="mt-3">
                      <div className="space-y-0">
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          Status: {p.status === "checked_in" ? "Til stede" : p.status === "checked_out" ? "Gået hjem" : p.status === "sick" ? "Syg" : p.status === "absent" ? "Fraværende" : "Ikke til stede"}
                          {p.location && ` (${p.location})`}
                        </p>
                        {p.check_in_time && (
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            Ankommet: {p.check_in_time.slice(0, 5)}
                            {p.check_out_time && ` — Gået: ${p.check_out_time.slice(0, 5)}`}
                          </p>
                        )}
                        {!p.check_in_time && p.planned_start && (
                          <p className="text-sm text-gray-400 dark:text-gray-500">
                            Planlagt: {p.planned_start.slice(0, 5)} — {p.planned_end?.slice(0, 5) || "?"}
                          </p>
                        )}
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          Hentetype: {p.exit_with || <span className="text-gray-400 dark:text-gray-500 italic">Ikke angivet</span>}{p.exit_with && p.planned_end && ` kl. ${p.planned_end.slice(0, 5)}`}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2 mt-3">
                        <button
                          onClick={() => openPickupForm(child.id)}
                          className="text-xs px-3 py-1 rounded-full bg-blue-600 text-white hover:bg-blue-700"
                        >
                          Hentetype
                        </button>
                        {p.status !== "sick" && (
                          <button
                            onClick={() => markSick(child.id, true)}
                            className="text-xs px-3 py-1 rounded-full bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400 hover:bg-orange-200 dark:hover:bg-orange-900/50"
                          >
                            Meld syg
                          </button>
                        )}
                        {p.status === "sick" && (
                          <button
                            onClick={() => markSick(child.id, false)}
                            className="text-xs px-3 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/50"
                          >
                            Rask igen
                          </button>
                        )}
                        {(p.status === "not_present" || p.status === "planned") && (
                          <button
                            onClick={() => updatePresence(child.id, "checked_in")}
                            className="text-xs px-3 py-1 rounded-full ml-auto bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-500 dark:border-green-600 hover:bg-green-200 dark:hover:bg-green-900/50"
                          >
                            Ankomst
                          </button>
                        )}
                        {p.status === "checked_in" && (
                          <button
                            onClick={() => updatePresence(child.id, "checked_out")}
                            className="text-xs px-3 py-1 rounded-full ml-auto bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-500 dark:border-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600"
                          >
                            Afgang
                          </button>
                        )}
                      </div>

                      {/* Pickup form */}
                      {pickupFormChild === child.id && (
                        <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 space-y-3">
                          <div>
                            <label className="text-xs font-medium text-gray-600 dark:text-gray-400 block mb-1">Hentetype</label>
                            <select
                              value={pickupType}
                              onChange={(e) => setPickupType(Number(e.target.value))}
                              className="w-full text-sm border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded px-2 py-1"
                            >
                              <option value={0}>Hentes af</option>
                              <option value={3}>Gå hjem med</option>
                              <option value={1}>Selvbestemmer</option>
                              <option value={2}>Send hjem</option>
                            </select>
                          </div>

                          {(pickupType === 0 || pickupType === 2 || pickupType === 3) && (
                            <div>
                              <label className="text-xs font-medium text-gray-600 dark:text-gray-400 block mb-1">Hentetid</label>
                              <input
                                type="time"
                                value={pickupExitTime}
                                onChange={(e) => setPickupExitTime(e.target.value)}
                                className="w-full text-sm border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded px-2 py-1"
                              />
                            </div>
                          )}

                          {(pickupType === 0) && (
                            <div>
                              <label className="text-xs font-medium text-gray-600 dark:text-gray-400 block mb-1">Hentes af</label>
                              <select
                                value={pickupExitWith}
                                onChange={(e) => setPickupExitWith(e.target.value)}
                                className="w-full text-sm border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded px-2 py-1"
                              >
                                {pickupResponsibles.map((r) => (
                                  <option key={r.id} value={`${r.name} (${r.relation})`}>
                                    {r.name} ({r.relation})
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}

                          {(pickupType === 3) && (
                            <div>
                              <label className="text-xs font-medium text-gray-600 dark:text-gray-400 block mb-1">Gå hjem med</label>
                              <select
                                value={pickupExitWith}
                                onChange={(e) => setPickupExitWith(e.target.value)}
                                className="w-full text-sm border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded px-2 py-1"
                              >
                                <option value="">Vælg barn...</option>
                                {goHomeWithList.map((c) => (
                                  <option key={c.id} value={`${c.name} (${c.group})`}>
                                    {c.name} ({c.group})
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}

                          <div className="flex gap-2">
                            <button
                              onClick={submitPickup}
                              disabled={pickupSubmitting}
                              className="text-xs px-3 py-1 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                            >
                              {pickupSubmitting ? "Gemmer..." : "Gem"}
                            </button>
                            <button
                              onClick={() => setPickupFormChild(null)}
                              className="text-xs px-3 py-1 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600"
                            >
                              Annullér
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* Messages & Posts Tabs */}
        <section>
          {children.length > 1 && (
            <div className="flex justify-end mb-6">
              <select
                value={childFilter}
                onChange={(e) => setChildFilter(e.target.value)}
                className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                <option value="all">Alle børn</option>
                {children.map((child) => (
                  <option key={child.id} value={child.profile_id}>
                    {child.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <button
                onClick={() => { setActiveTab("messages"); setSelectedPost(null); }}
                className={`inline-flex items-center text-lg font-semibold ${activeTab === "messages" ? "text-gray-900 dark:text-white" : "text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"}`}
              >
                <span className={activeTab === "messages" ? "underline underline-offset-4" : ""}>Beskeder</span>
                {messages.filter((m) => !m.is_read).length > 0 && (
                  <span className="ml-2 px-2 py-0.5 text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-full">
                    {messages.filter((m) => !m.is_read).length}
                  </span>
                )}
              </button>
              <button
                onClick={() => { setActiveTab("posts"); setSelectedThread(null); }}
                className={`inline-flex items-center text-lg font-semibold ${activeTab === "posts" ? "text-gray-900 dark:text-white" : "text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"}`}
              >
                <span className={activeTab === "posts" ? "underline underline-offset-4" : ""}>Opslag</span>
                {posts.filter((p) => !p.is_read).length > 0 && (
                  <span className="ml-2 px-2 py-0.5 text-xs bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400 rounded-full">
                    {posts.filter((p) => !p.is_read).length}
                  </span>
                )}
              </button>
              <button
                onClick={() => { setActiveTab("vacation"); setSelectedThread(null); setSelectedPost(null); }}
                className={`inline-flex items-center text-lg font-semibold ${activeTab === "vacation" ? "text-gray-900 dark:text-white" : "text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"}`}
              >
                <span className={activeTab === "vacation" ? "underline underline-offset-4" : ""}>Ferie</span>
                {vacations.filter((v) => v.is_missing_answer).length > 0 && (
                  <span className="ml-2 px-2 py-0.5 text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-full">
                    {vacations.filter((v) => v.is_missing_answer).length}
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* Thread detail view */}
          {activeTab === "messages" && selectedThread && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900 mb-4">
              <div className="p-4 flex items-center justify-between">
                <h3 className="font-medium text-gray-900 dark:text-white">{selectedThread.subject || "(ingen emne)"}</h3>
                <button
                  onClick={() => setSelectedThread(null)}
                  className="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition leading-none"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                  </svg>
                  Tilbage
                </button>
              </div>
              <div className="mx-5"><hr className="border-gray-200 dark:border-gray-700" /></div>
              <div className="max-h-96 overflow-y-auto">
                {selectedThread.messages.map((m, i) => (
                  <div key={m.id}>
                    {i > 0 && (
                      <div className="mx-6">
                        <hr className="border-gray-200 dark:border-gray-700" />
                      </div>
                    )}
                    <div className="p-4">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{m.sender}</span>
                        <time className="text-xs text-gray-400 dark:text-gray-500">
                          {new Date(m.timestamp).toLocaleString("da-DK")}
                        </time>
                      </div>
                      <div
                        className="text-sm text-gray-700 dark:text-gray-300 prose prose-sm dark:prose-invert max-w-none"
                        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.text) }}
                      />
                      {m.attachments && m.attachments.length > 0 && (
                        <div className="mt-3 space-y-1">
                          {m.attachments.map((att) => (
                            <a
                              key={att.id}
                              href={getAttachmentHref(att.url, att.name)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:underline"
                            >
                              <span className="text-gray-400 dark:text-gray-500">📎</span>
                              {att.name}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Thread list */}
          {activeTab === "messages" && !selectedThread && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900">
            {filteredMessages.length === 0 && (
              <p className="p-4 text-gray-500 dark:text-gray-400">Ingen beskeder</p>
            )}
            {filteredMessages.map((msg, i) => (
              <div key={msg.id}>
                {i > 0 && (
                  <div className="mx-5">
                    <hr className="border-gray-200 dark:border-gray-700" />
                  </div>
                )}
                <div
                  className={`p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition ${!msg.is_read ? "bg-blue-50 dark:bg-blue-900/30" : ""}`}
                  onClick={() => openThread(msg)}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {!msg.is_read && (
                          <span className="w-2 h-2 bg-blue-600 rounded-full flex-shrink-0" />
                        )}
                        <p className={`text-gray-900 dark:text-white truncate ${!msg.is_read ? "font-semibold" : "font-medium"}`}>
                          {msg.subject || "(ingen emne)"}
                        </p>
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">Fra: {msg.sender}</p>
                      {msg.preview && (
                        <p className="text-sm text-gray-400 dark:text-gray-500 truncate mt-1">
                          {msg.preview.replace(/<[^>]*>/g, "")}
                        </p>
                      )}
                    </div>
                      <div className="flex flex-col items-end ml-4 gap-1">
                      <time className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                        {msg.timestamp ? new Date(msg.timestamp).toLocaleDateString("da-DK") : ""}
                      </time>
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleReadStatus(msg); }}
                        className={`text-xs whitespace-nowrap px-2 py-0.5 rounded-full transition ${msg.is_read ? "bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600" : "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium hover:bg-gray-200 dark:hover:bg-gray-700"}`}
                        title={msg.is_read ? "Markér som ulæst" : "Markér som læst"}
                      >
                        {msg.is_read ? "Læst" : "Ulæst"}
                      </button>
                      {msg.attachments && msg.attachments.length > 0 && (
                        <span className="text-xs text-gray-400 dark:text-gray-500">📎 {msg.attachments.length}</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          )}
          {activeTab === "messages" && threadLoading && (
            <div className="flex justify-center mt-4">
              <div className="animate-spin w-6 h-6 border-4 border-blue-600 border-t-transparent rounded-full" />
            </div>
          )}

          {/* Posts / Opslag tab */}
          {activeTab === "posts" && selectedPost && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900 mb-4">
              <div className="p-4 flex items-center justify-between">
                <h3 className="font-medium text-gray-900 dark:text-white">{selectedPost.title}</h3>
                <button
                  onClick={() => setSelectedPost(null)}
                  className="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition leading-none"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                  </svg>
                  Tilbage
                </button>
              </div>
              <div className="mx-5"><hr className="border-gray-200 dark:border-gray-700" /></div>
              <div className="p-4">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {selectedPost.sender} · {selectedPost.institution}
                  </span>
                  <time className="text-xs text-gray-400 dark:text-gray-500">
                    {new Date(selectedPost.timestamp).toLocaleString("da-DK")}
                  </time>
                </div>
                <div
                  className="text-sm text-gray-700 dark:text-gray-300 prose prose-sm dark:prose-invert max-w-none"
                  dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(selectedPost.content) }}
                />
                {selectedPost.attachments.length > 0 && (
                  <div className="mt-4 space-y-1">
                    {selectedPost.attachments.map((att) => (
                      <a
                        key={att.id}
                        href={getAttachmentHref(att.url, att.name)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:underline"
                      >
                        <span className="text-gray-400 dark:text-gray-500">📎</span>
                        {att.name}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "posts" && !selectedPost && (
          <>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900">
            {filteredPosts.length === 0 && (
              <p className="p-4 text-gray-500 dark:text-gray-400">Ingen opslag</p>
            )}
            {filteredPosts.map((post, i) => (
              <div key={post.id}>
                {i > 0 && (
                  <div className="mx-5">
                    <hr className="border-gray-200 dark:border-gray-700" />
                  </div>
                )}
                <div
                  className={`p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition ${!post.is_read ? "bg-blue-50 dark:bg-blue-900/30" : ""} ${post.is_important ? "border-l-4 border-orange-400" : ""}`}
                  onClick={() => {
                    listScrollPos.current = window.scrollY;
                    setSelectedPost(post);
                    if (!post.is_read) {
                      // Mark as read locally and notify the backend.
                      setPosts((prev) => prev.map((p) => p.id === post.id ? { ...p, is_read: true } : p));
                      api.markPostRead(post.id).catch(() => {/* fire-and-forget */});
                    }
                  }}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {!post.is_read && (
                          <span className="w-2 h-2 bg-blue-600 rounded-full flex-shrink-0" />
                        )}
                        {post.is_important && (
                          <span className="text-orange-500 dark:text-orange-400 text-xs font-medium">⚠ Vigtigt</span>
                        )}
                        <p className={`text-gray-900 dark:text-white truncate ${!post.is_read ? "font-semibold" : "font-medium"}`}>
                          {post.title}
                        </p>
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                        {post.sender} · {post.institution}
                      </p>
                      <p className="text-sm text-gray-400 dark:text-gray-500 truncate mt-1">
                        {post.content.replace(/<[^>]*>/g, "").slice(0, 100)}
                      </p>
                    </div>
                    <div className="flex flex-col items-end ml-4">
                      <time className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                        {post.timestamp ? new Date(post.timestamp).toLocaleDateString("da-DK") : ""}
                      </time>
                      <button
                        onClick={(e) => { e.stopPropagation(); togglePostReadStatus(post); }}
                        className={`text-xs mt-1 px-2 py-0.5 rounded-full ${post.is_read ? "bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600" : "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium hover:bg-blue-200 dark:hover:bg-blue-900/50"}`}
                      >
                        {post.is_read ? "Læst" : "Ulæst"}
                      </button>
                      {post.attachments.length > 0 && (
                        <span className="text-xs text-gray-400 dark:text-gray-500 mt-1">📎 {post.attachments.length}</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {posts.some((p) => !p.is_read) && (
            <div className="mt-2 flex justify-end">
              <button
                onClick={markAllPostsRead}
                className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 underline underline-offset-2"
              >
                Markér alle som læst
              </button>
            </div>
          )}
          </>
          )}

          {/* Vacation / Ferie tab */}
          {activeTab === "vacation" && selectedVacation && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900 mb-4">
              <div className="p-4 flex items-center justify-between">
                <h3 className="font-medium text-gray-900 dark:text-white">{selectedVacation.title} — {selectedVacation.child_name}</h3>
                <button
                  onClick={() => setSelectedVacation(null)}
                  className="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition leading-none"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                  </svg>
                  Tilbage
                </button>
              </div>
              <div className="mx-5"><hr className="border-gray-200 dark:border-gray-700" /></div>
              <div className="p-4">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                  {new Date(selectedVacation.start_date).toLocaleDateString("da-DK")} – {new Date(selectedVacation.end_date).toLocaleDateString("da-DK")}
                </p>
                <p className="text-sm text-gray-400 dark:text-gray-500 mb-4">Frist: {new Date(selectedVacation.deadline).toLocaleDateString("da-DK")}</p>
                {selectedVacation.note && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 italic mb-4">{selectedVacation.note}</p>
                )}
                <div className="space-y-2">
                  {vacationDays.map((day, idx) => {
                    const date = new Date(day.date);
                    // Get ISO week number
                    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
                    d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
                    const weekNum = Math.ceil((((d.getTime() - new Date(Date.UTC(d.getUTCFullYear(), 0, 1)).getTime()) / 86400000) + 1) / 7);
                    // Show week header on first day or when week changes
                    let showWeekHeader = idx === 0;
                    if (idx > 0) {
                      const prevDate = new Date(vacationDays[idx - 1].date);
                      const pd = new Date(Date.UTC(prevDate.getFullYear(), prevDate.getMonth(), prevDate.getDate()));
                      pd.setUTCDate(pd.getUTCDate() + 4 - (pd.getUTCDay() || 7));
                      const prevWeek = Math.ceil((((pd.getTime() - new Date(Date.UTC(pd.getUTCFullYear(), 0, 1)).getTime()) / 86400000) + 1) / 7);
                      showWeekHeader = weekNum !== prevWeek;
                    }
                    return (
                      <div key={day.date}>
                        {showWeekHeader && (
                          <div className={`text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wide ${idx > 0 ? "mt-3" : ""} mb-1`}>
                            Uge {weekNum}
                          </div>
                        )}
                        <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-700/50">
                          <span className="text-sm text-gray-700 dark:text-gray-300">
                            {date.toLocaleDateString("da-DK", { weekday: "short", day: "numeric", month: "short" })}
                          </span>
                          <div className="flex gap-2">
                            <button
                              onClick={() => setVacationDays((prev) => prev.map((d, i) => i === idx ? { ...d, isComing: true } : d))}
                              className={`text-xs px-3 py-1 rounded-full ${day.isComing ? "bg-green-600 text-white" : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300"}`}
                            >
                              Kommer
                            </button>
                            <button
                              onClick={() => setVacationDays((prev) => prev.map((d, i) => i === idx ? { ...d, isComing: false } : d))}
                              className={`text-xs px-3 py-1 rounded-full ${!day.isComing ? "bg-red-600 text-white" : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300"}`}
                            >
                              Fri
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
                {selectedVacation.is_editable && (
                  <div className="mt-4 flex gap-2">
                    <button
                      onClick={() => setVacationDays((prev) => prev.map((d) => ({ ...d, isComing: true })))}
                      className="text-xs px-3 py-1.5 rounded-lg bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/50"
                    >
                      Alle kommer
                    </button>
                    <button
                      onClick={() => setVacationDays((prev) => prev.map((d) => ({ ...d, isComing: false })))}
                      className="text-xs px-3 py-1.5 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/50"
                    >
                      Alle fri
                    </button>
                    <button
                      onClick={submitVacation}
                      disabled={vacationSubmitting}
                      className="ml-auto text-sm px-4 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {vacationSubmitting ? "Sender..." : "Indsend"}
                    </button>
                  </div>
                )}
                {!selectedVacation.is_editable && (
                  <p className="mt-4 text-sm text-gray-400 dark:text-gray-500 italic">Denne registrering kan ikke redigeres.</p>
                )}
              </div>
            </div>
          )}

          {activeTab === "vacation" && !selectedVacation && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900">
            {filteredVacations.length === 0 && (
              <p className="p-4 text-gray-500 dark:text-gray-400">Ingen ferieregistreringer</p>
            )}
            {filteredVacations.map((vac, i) => (
              <div key={`${vac.id}-${vac.child_id}`}>
                {i > 0 && (
                  <div className="mx-5">
                    <hr className="border-gray-200 dark:border-gray-700" />
                  </div>
                )}
                <div
                  className={`p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition ${vac.is_missing_answer ? "bg-yellow-50 dark:bg-yellow-900/20" : ""}`}
                  onClick={() => openVacation(vac)}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {vac.is_missing_answer && (
                          <span className="w-2 h-2 bg-red-500 rounded-full flex-shrink-0" />
                        )}
                        <p className={`text-gray-900 dark:text-white ${vac.is_missing_answer ? "font-semibold" : "font-medium"}`}>
                          {vac.title}
                        </p>
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                        {vac.child_name}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {new Date(vac.start_date).toLocaleDateString("da-DK")} – {new Date(vac.end_date).toLocaleDateString("da-DK")}
                      </p>
                      {vac.note && (
                        <p className="text-sm text-gray-400 dark:text-gray-500 mt-1 italic">
                          {vac.note}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-col items-end ml-4">
                      <time className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                        Frist: {new Date(vac.deadline).toLocaleDateString("da-DK")}
                      </time>
                      <span className={`text-xs mt-1 px-2 py-0.5 rounded-full ${vac.is_missing_answer ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 font-medium" : "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"}`}>
                        {vac.is_missing_answer ? "Mangler svar" : "Besvaret"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          )}
        </section>
      </main>
      {/* Toast notifications */}
      {toasts.length > 0 && (
        <div className="fixed bottom-4 right-4 z-50 space-y-2">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={`px-4 py-2 rounded-lg shadow-lg dark:shadow-gray-900 text-sm font-medium animate-fade-in ${
                toast.type === "error"
                  ? "bg-red-600 text-white"
                  : "bg-green-600 text-white"
              }`}
            >
              {toast.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
