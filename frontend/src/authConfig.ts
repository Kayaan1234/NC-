// Mirrors the throttle/TTL values in backend/core/config.py. These are display
// hints only (the backend always enforces the real limits). They're hardcoded
// here because the API exposes no config endpoint — if those settings change,
// update these too. A future /auth/config endpoint would remove the drift risk.

export const VERIFICATION_TTL_HOURS = 24 // VERIFICATION_TTL_HOURS
export const RESEND_COOLDOWN_MINUTES = 10 // VERIFICATION_RESEND_COOLDOWN_MINUTES
export const EMAIL_CHANGE_COOLDOWN_HOURS = 24 // EMAIL_CHANGE_COOLDOWN_HOURS
