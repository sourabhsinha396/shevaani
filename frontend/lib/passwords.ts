/**
 * Mirrors `PASSWORD_MIN_LENGTH` in `backend/app/schemas/auth.py`.
 *
 * The server is what actually enforces this — every form below can be bypassed.
 * Keeping it here is so the three screens that set a password (register, reset,
 * account) show the same number and reject early, instead of each carrying its
 * own copy and drifting apart the next time the rule changes.
 */
export const PASSWORD_MIN_LENGTH = 8;

export const PASSWORD_HINT = `At least ${PASSWORD_MIN_LENGTH} characters.`;
