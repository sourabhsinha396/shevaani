import type {
  AdminInstructor,
  AdminSession,
  Availability,
  AvailabilitySummary,
  Block,
  BillingProfile,
  Booking,
  BookingWithSession,
  CancellationImpact,
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
  PaymentProvider,
  Roster,
  SiteConfig,
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
    starts_before?: string;
    include_full?: boolean;
    limit?: number;
  } = {}) => request<DiscussionSession[]>(`/sessions${qs(params)}`),

  getSession: (id: string) => request<DiscussionSession>(`/sessions/${id}`),

  bookSession: (id: string, allowWaitlist = true) =>
    request<Booking>(`/sessions/${id}/book${qs({ allow_waitlist: allowWaitlist })}`, {
      method: "POST",
    }),

  /** Records that somebody actually went, and hands back the link. The link is
   *  also on every booking from `myBookings`, so the dashboard opens that and
   *  calls this only for the audit row and the attendance signal. Resolves for
   *  a confirmed booking on either kind of session, until the session ends. */
  joinSession: (id: string) => request<JoinInfo>(`/sessions/${id}/join`),

  // ---- bookings
  /** Both kinds, group and one-to-one, each carrying its Meet link. */
  myBookings: (upcoming = true) =>
    request<BookingWithSession[]>(`/bookings${qs({ upcoming })}`),

  cancelBooking: (id: string, reason?: string) =>
    request<Booking>(`/bookings/${id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  /** No `instructor_id`: the server picks somebody free at that hour, at random,
   *  and retries with the next candidate if the pick loses a race. */
  bookOneOnOne: (payload: {
    starts_at: string;
    duration_minutes?: number;
    instructor_id?: string;
  }) =>
    request<Booking>("/bookings/one-on-one", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  creditBalance: () => request<{ balance: number }>("/bookings/credits/balance"),

  creditLedger: (limit = 50) =>
    request<LedgerEntry[]>(`/bookings/credits/ledger${qs({ limit })}`),

  // ---- billing
  /** `currency` is what the browser detected; the response echoes back what the
   *  server actually resolved it to, which may be USD. */
  billingProfile: (currency?: string) =>
    request<BillingProfile>(`/billing/profile${qs({ currency })}`),

  /** The price list. Public — no account needed, which is what lets `/pricing`
   *  show real numbers instead of a hand-copied duplicate. Every pack carries
   *  the full `prices` map, so `currency` only picks the convenience field. */
  creditPacks: (currency?: string) =>
    request<CreditPack[]>(`/billing/packs${qs({ currency })}`),

  /** Opens an order. Grants nothing. The currency is a code and never an
   *  amount: the server re-quotes the price itself. */
  startCheckout: (packId: string, currency?: string, provider?: PaymentProvider) =>
    request<CheckoutSession>("/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ pack_id: packId, currency, provider }),
    }),

  /** Asks the server to settle a payment against the provider. This is what
   *  actually grants credits, so the return page calls it rather than polling
   *  for a webhook to land. Idempotent — calling it twice grants once.
   *
   *  The Razorpay fields come from its modal and are omitted for Stripe, which
   *  returns by redirect with nothing signed to pass on. Neither is trusted on
   *  its own: the server re-fetches the order either way. */
  verifyPayment: (
    id: string,
    payload: { razorpay_payment_id?: string; razorpay_signature?: string } = {},
  ) =>
    request<Payment>(`/billing/payments/${id}/verify`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  payment: (id: string) => request<Payment>(`/billing/payments/${id}`),

  myPayments: () => request<Payment[]>("/billing/payments"),

  // ---- instructors
  listInstructors: () => request<Instructor[]>("/instructors"),

  /** Open one-to-one times across the whole team, a month per request — the
   *  calendar has to know which dates are bookable before one is clicked. */
  availability: (params: { from?: string; days?: number; duration_minutes?: number } = {}) =>
    request<Availability>(`/instructors/availability${qs(params)}`),

  /** Is 1:1 bookable at all? Cheap enough for the header to ask on every load. */
  availabilitySummary: (days?: number) =>
    request<AvailabilitySummary>(`/instructors/availability/summary${qs({ days })}`),

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

  /** Read fresh, not through the ISR cache the rest of the site sees — a
   *  settings screen that is a minute behind reports your own save as having
   *  not happened. See `lib/site-config.ts` for the cached read. */
  adminSiteConfig: () => request<SiteConfig>("/admin/config"),

  /** Partial: send only the switch that moved. */
  adminUpdateSiteConfig: (payload: Partial<SiteConfig>) =>
    request<SiteConfig>("/admin/config", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  adminContactMessages: (handled?: boolean) =>
    request<ContactMessage[]>(`/admin/contact-messages${qs({ handled })}`),

  adminMarkContactHandled: (id: string, note?: string) =>
    request<{ detail: string }>(`/admin/contact-messages/${id}/handled`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
};
