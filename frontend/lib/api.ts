import type {
  AdminFacilitator,
  AdminSession,
  Block,
  Booking,
  BookingWithSession,
  CEFRLevel,
  DiscussionSession,
  Facilitator,
  JoinInfo,
  Slot,
  User,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PREFIX = `${BASE}/api/v1`;

/** Mirrors the backend's `{ detail, code }` error shape so callers can branch on
 *  a stable code rather than parsing prose. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${PREFIX}${path}`, {
    ...init,
    // Auth is an httpOnly cookie — nothing is ever kept in localStorage.
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  if (response.status === 204) return undefined as T;

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      body?.detail ?? `Request failed (${response.status})`,
      response.status,
      body?.code,
    );
  }
  return body as T;
}

const qs = (params: Record<string, string | number | boolean | undefined>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const out = search.toString();
  return out ? `?${out}` : "";
};

export const api = {
  // ---- auth
  register: (payload: {
    email: string;
    password: string;
    full_name: string;
    timezone?: string;
    billing_country?: string;
  }) =>
    request<{ user: User; access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: (payload: { email: string; password: string }) =>
    request<{ user: User; access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  logout: () => request<{ detail: string }>("/auth/logout", { method: "POST" }),

  me: () => request<User>("/auth/me"),

  // ---- catalogue
  listDiscussions: (params: {
    level?: CEFRLevel;
    starts_before?: string;
    include_full?: boolean;
    limit?: number;
  } = {}) =>
    request<DiscussionSession[]>(
      `/sessions${qs({ kind: "group", ...params })}`,
    ),

  getSession: (id: string) => request<DiscussionSession>(`/sessions/${id}`),

  bookSession: (id: string, allowWaitlist = true) =>
    request<Booking>(`/sessions/${id}/book${qs({ allow_waitlist: allowWaitlist })}`, {
      method: "POST",
    }),

  /** Only resolves inside the join window, and only for a confirmed booking. */
  joinSession: (id: string) => request<JoinInfo>(`/sessions/${id}/join`),

  // ---- bookings
  myBookings: (upcoming = true) =>
    request<BookingWithSession[]>(`/bookings${qs({ upcoming })}`),

  cancelBooking: (id: string, reason?: string) =>
    request<Booking>(`/bookings/${id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  bookOneOnOne: (payload: {
    facilitator_id: string;
    starts_at: string;
    duration_minutes?: number;
  }) =>
    request<Booking>("/bookings/one-on-one", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  creditBalance: () => request<{ balance: number }>("/bookings/credits/balance"),

  // ---- facilitators
  listFacilitators: () => request<Facilitator[]>("/facilitators"),

  /** `date` is a local calendar date (YYYY-MM-DD) in the booking timezone. */
  slots: (facilitatorId: string, date: string, durationMinutes?: number) =>
    request<Slot[]>(
      `/facilitators/${facilitatorId}/slots${qs({
        date,
        duration_minutes: durationMinutes,
      })}`,
    ),

  listBlocks: (facilitatorId: string, until?: string) =>
    request<Block[]>(`/facilitators/${facilitatorId}/blocks${qs({ until })}`),

  createBlock: (
    facilitatorId: string,
    payload: { starts_at: string; ends_at: string; reason?: string; note?: string },
  ) =>
    request<Block>(`/facilitators/${facilitatorId}/blocks`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  deleteBlock: (facilitatorId: string, blockId: string) =>
    request<{ detail: string }>(`/facilitators/${facilitatorId}/blocks/${blockId}`, {
      method: "DELETE",
    }),

  googleStatus: () =>
    request<{ connected: boolean; google_email: string | null; connected_at: string | null }>(
      "/facilitators/google/status",
    ),

  googleConnectUrl: () => `${PREFIX}/facilitators/google/connect`,

  // ---- admin
  adminListSessions: (params: { status?: string; kind?: string } = {}) =>
    request<AdminSession[]>(`/admin/sessions${qs(params)}`),

  adminCreateSession: (payload: Record<string, unknown>) =>
    request<AdminSession>("/admin/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  adminUpdateSession: (id: string, payload: Record<string, unknown>) =>
    request<AdminSession>(`/admin/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  adminPublish: (id: string) =>
    request<AdminSession>(`/admin/sessions/${id}/publish`, { method: "POST" }),

  adminCancel: (id: string, reason: string) =>
    request<AdminSession>(`/admin/sessions/${id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  adminRetryMeeting: (id: string) =>
    request<{ detail: string }>(`/admin/sessions/${id}/retry-meeting`, { method: "POST" }),

  adminRoster: (id: string) =>
    request<{
      confirmed: Array<{
        booking_id: string;
        name: string;
        email: string;
        level: string | null;
        first_joined_at: string | null;
        attendance_confirmed_at: string | null;
      }>;
      waitlist: Array<{ booking_id: string; name: string; position: number }>;
    }>(`/admin/sessions/${id}/roster`),

  adminFacilitators: () => request<AdminFacilitator[]>("/admin/facilitators"),
};
