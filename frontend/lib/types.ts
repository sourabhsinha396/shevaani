export type CEFRLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export type UserRole = "learner" | "instructor" | "superuser";

export type SessionStatus = "draft" | "published" | "cancelled" | "completed";

export type BookingStatus =
  | "pending"
  | "confirmed"
  | "waitlisted"
  | "cancelled"
  | "attended"
  | "no_show";

export type MeetingStatus = "pending" | "ready" | "failed";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  timezone: string;
  /** Null while unconfirmed. Advisory only — nothing is blocked by it. */
  email_verified_at: string | null;
  level: CEFRLevel | null;
  headline: string | null;
  bio: string | null;
}

export type PaymentProvider = "stripe" | "razorpay";

export type PaymentStatus = "created" | "paid" | "failed" | "refunded";

export interface CreditPack {
  id: string;
  slug: string;
  name: string;
  credits: number;
  /** Paise or cents — never a float. Format it, don't do arithmetic on it. */
  amount_minor: number;
  currency: string;
}

export interface BillingProfile {
  currency: string;
  provider: PaymentProvider;
  /** False while the provider's keys are missing or its adapter is a stub. */
  provider_ready: boolean;
}

export interface CheckoutSession {
  payment_id: string;
  provider: PaymentProvider;
  amount_minor: number;
  currency: string;
  credits: number;
  /** Stripe hands back a URL; Razorpay hands back a modal payload. One or the other. */
  redirect_url: string | null;
  client_payload: Record<string, unknown>;
}

export interface Payment {
  id: string;
  provider: PaymentProvider;
  status: PaymentStatus;
  amount_minor: number;
  currency: string;
  credits: number;
  created_at: string;
  paid_at: string | null;
  failure_reason: string | null;
}

export interface Instructor {
  id: string;
  full_name: string;
  headline: string | null;
  bio: string | null;
}

export type SessionKind = "group" | "one_on_one";

export interface DiscussionSession {
  id: string;
  kind: SessionKind;
  title: string;
  topic: string | null;
  description: string | null;
  prep_material_url: string | null;
  level_min: CEFRLevel;
  level_max: CEFRLevel;
  starts_at: string;
  ends_at: string;
  min_seats: number;
  max_seats: number;
  price_credits: number;
  status: SessionStatus;
  instructor: Instructor;
  seats_taken: number;
  seats_left: number;
  is_full: boolean;
  my_booking_status: BookingStatus | null;
}

export interface AdminSession extends DiscussionSession {
  meeting_status: MeetingStatus | null;
  meeting_last_error: string | null;
  meeting_host_email: string | null;
  waitlist_count: number;
}

export interface Booking {
  id: string;
  session_id: string;
  status: BookingStatus;
  starts_at: string;
  ends_at: string;
  credits_spent: number;
  waitlist_position: number | null;
}

export interface BookingWithSession extends Booking {
  session: DiscussionSession;
}

export interface Slot {
  starts_at: string;
  ends_at: string;
}

export interface Block {
  id: string;
  instructor_id: string;
  starts_at: string;
  ends_at: string;
  reason: "busy" | "holiday" | "sick" | "other";
  note: string | null;
}

export interface AdminInstructor {
  id: string;
  full_name: string;
  email: string;
  is_active: boolean;
  headline: string | null;
  bio: string | null;
  google_connected: boolean;
  google_email: string | null;
  upcoming_sessions: number;
}

export interface RosterEntry {
  booking_id: string;
  learner_id: string;
  name: string;
  /** Null on the instructor's own roster — they get names, not contact details. */
  email: string | null;
  level: CEFRLevel | null;
  status: BookingStatus;
  first_joined_at: string | null;
  attendance_confirmed_at: string | null;
}

export interface Roster {
  confirmed: RosterEntry[];
  waitlist: Array<{
    booking_id: string;
    learner_id: string;
    name: string;
    position: number;
  }>;
}

/** What cancelling a session would cost — shown before the button is pressed. */
export interface CancellationImpact {
  bookings_affected: number;
  learners_refunded: number;
  credits_refunded: number;
  waitlisted: number;
}

export interface LearnerSummary {
  id: string;
  full_name: string;
  email: string;
  level: CEFRLevel | null;
  is_active: boolean;
  timezone: string;
  created_at: string;
  balance: number;
  upcoming_bookings: number;
}

export type CreditReason =
  | "purchase"
  | "booking_spend"
  | "booking_refund"
  | "session_cancelled"
  | "admin_grant"
  | "admin_revoke";

export interface LedgerEntry {
  id: string;
  delta: number;
  reason: CreditReason;
  note: string | null;
  booking_id: string | null;
  payment_id: string | null;
  created_at: string;
}

export interface LearnerBooking {
  id: string;
  session_id: string;
  session_title: string;
  status: BookingStatus;
  starts_at: string;
  ends_at: string;
  credits_spent: number;
  waitlist_position: number | null;
  cancelled_at: string | null;
}

export interface LearnerDetail {
  learner: LearnerSummary;
  bookings: LearnerBooking[];
  ledger: LedgerEntry[];
}

export interface ContactMessage {
  id: string;
  name: string;
  email: string;
  subject: string;
  body: string;
  user_id: string | null;
  created_at: string;
  handled_at: string | null;
  handled_note: string | null;
}

export interface JoinInfo {
  join_url: string;
  session_id: string;
  starts_at: string;
  ends_at: string;
}
