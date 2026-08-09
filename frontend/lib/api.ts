import type {
  AdminInstructor,
  AdminSession,
  Block,
  BillingProfile,
  Booking,
  BookingWithSession,
  CancellationImpact,
  CEFRLevel,
  CheckoutSession,
  ContactMessage,
  CreditPack,
  DiscussionSession,
  Instructor,
  JoinInfo,
  LearnerDetail,
  LearnerSummary,
  LedgerEntry,
  Payment,
  Roster,
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

  /** Always resolves with the same message, registered address or not. */
  forgotPassword: (email: string) =>
    request<{ detail: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  /** Signs the browser in on success — the mailbox has just been proven. */
  resetPassword: (token: string, password: string) =>
    request<{ user: User; access_token: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),

  /** Signs every *other* browser out. This one gets fresh cookies back. */
  changePassword: (current_password: string, new_password: string) =>
    request<{ user: User; access_token: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),

  sendEmailVerification: () =>
    request<{ detail: string }>("/auth/verify-email/send", { method: "POST" }),

  verifyEmail: (token: string) =>
    request<User>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

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
    instructor_id: string;
    starts_at: string;
    duration_minutes?: number;
  }) =>
    request<Booking>("/bookings/one-on-one", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  creditBalance: () => request<{ balance: number }>("/bookings/credits/balance"),

  creditLedger: (limit = 50) =>
    request<LedgerEntry[]>(`/bookings/credits/ledger${qs({ limit })}`),

  // ---- billing
  billingProfile: () => request<BillingProfile>("/billing/profile"),

  /** Packs the caller can buy, already narrowed to their billing currency. */
  creditPacks: () => request<CreditPack[]>("/billing/packs"),

  /** Opens an order. Grants nothing — only the webhook does that. */
  startCheckout: (packId: string) =>
    request<CheckoutSession>("/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ pack_id: packId }),
    }),

  payment: (id: string) => request<Payment>(`/billing/payments/${id}`),

  myPayments: () => request<Payment[]>("/billing/payments"),

  // ---- instructors
  listInstructors: () => request<Instructor[]>("/instructors"),

  /** `date` is a local calendar date (YYYY-MM-DD) in the booking timezone. */
  slots: (instructorId: string, date: string, durationMinutes?: number) =>
    request<Slot[]>(
      `/instructors/${instructorId}/slots${qs({
        date,
        duration_minutes: durationMinutes,
      })}`,
    ),

  listBlocks: (instructorId: string, until?: string) =>
    request<Block[]>(`/instructors/${instructorId}/blocks${qs({ until })}`),

  createBlock: (
    instructorId: string,
    payload: { starts_at: string; ends_at: string; reason?: string; note?: string },
  ) =>
    request<Block>(`/instructors/${instructorId}/blocks`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  deleteBlock: (instructorId: string, blockId: string) =>
    request<{ detail: string }>(`/instructors/${instructorId}/blocks/${blockId}`, {
      method: "DELETE",
    }),

  googleStatus: () =>
    request<{ connected: boolean; google_email: string | null; connected_at: string | null }>(
      "/instructors/google/status",
    ),

  googleConnectUrl: () => `${PREFIX}/instructors/google/connect`,

  // ---- contact
  contact: (payload: {
    name: string;
    email: string;
    subject: string;
    body: string;
  }) =>
    request<{ detail: string }>("/contact", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ---- the instructor's own work (scoped server-side to the caller)
  myInstructorSessions: () => request<AdminSession[]>("/instructors/me/sessions"),

  myInstructorRoster: (sessionId: string) =>
    request<Roster>(`/instructors/me/sessions/${sessionId}/roster`),

  myConfirmAttendance: (bookingId: string, attended: boolean) =>
    request<{ detail: string }>(
      `/instructors/me/bookings/${bookingId}/attendance${qs({ attended })}`,
      { method: "POST" },
    ),

  // ---- admin
  adminListSessions: (params: { status?: string; kind?: string } = {}) =>
    request<AdminSession[]>(`/admin/sessions${qs(params)}`),

  adminGetSession: (id: string) => request<AdminSession>(`/admin/sessions/${id}`),

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

  adminRoster: (id: string) => request<Roster>(`/admin/sessions/${id}/roster`),

  /** What cancelling would cost, for the confirm dialog. */
  adminCancellationImpact: (id: string) =>
    request<CancellationImpact>(`/admin/sessions/${id}/cancellation-impact`),

  adminReschedule: (id: string, payload: { starts_at: string; duration_minutes?: number }) =>
    request<AdminSession>(`/admin/sessions/${id}/reschedule`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  adminAttendance: (bookingId: string, attended: boolean) =>
    request<{ detail: string }>(
      `/admin/bookings/${bookingId}/attendance${qs({ attended })}`,
      { method: "POST" },
    ),

  adminInstructors: () => request<AdminInstructor[]>("/admin/instructors"),

  adminUpdateInstructor: (
    id: string,
    payload: { full_name?: string; headline?: string | null; bio?: string | null; is_active?: boolean },
  ) =>
    request<{ detail: string }>(`/admin/instructors/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  adminLearners: (query?: string) =>
    request<LearnerSummary[]>(`/admin/learners${qs({ query })}`),

  adminLearner: (id: string) => request<LearnerDetail>(`/admin/learners/${id}`),

  /** Signed: positive grants, negative claws back. Both are ledger rows. */
  adminAdjustCredits: (id: string, delta: number, note?: string) =>
    request<{ balance: number }>(`/admin/learners/${id}/credits`, {
      method: "POST",
      body: JSON.stringify({ delta, note }),
    }),

  adminContactMessages: (handled?: boolean) =>
    request<ContactMessage[]>(`/admin/contact-messages${qs({ handled })}`),

  adminMarkContactHandled: (id: string, note?: string) =>
    request<{ detail: string }>(`/admin/contact-messages/${id}/handled`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
};
