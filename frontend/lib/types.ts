export type CEFRLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export type UserRole = "learner" | "facilitator" | "superuser";

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
  level: CEFRLevel | null;
  headline: string | null;
  bio: string | null;
}

export interface Facilitator {
  id: string;
  full_name: string;
  headline: string | null;
  bio: string | null;
}

export interface DiscussionSession {
  id: string;
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
  facilitator: Facilitator;
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
  facilitator_id: string;
  starts_at: string;
  ends_at: string;
  reason: "busy" | "holiday" | "sick" | "other";
  note: string | null;
}

export interface AdminFacilitator {
  id: string;
  full_name: string;
  email: string;
  is_active: boolean;
  google_connected: boolean;
  google_email: string | null;
}

export interface JoinInfo {
  join_url: string;
  session_id: string;
  starts_at: string;
  ends_at: string;
}
