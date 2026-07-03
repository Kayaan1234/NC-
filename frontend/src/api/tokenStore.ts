// --- Token storage ---------------------------------------------------------
//
// SECURITY NOTE (surfaced to the developer, not a silent decision):
// The access token is held ONLY in memory (a module-level variable); the refresh
// token lives ONLY in an httpOnly, Secure, SameSite=Strict cookie set by the
// backend. Nothing auth-related is persisted to localStorage anymore, so an XSS
// bug has no stored token to read or exfiltrate. Consequence (by design): a full
// page reload wipes the in-memory access token, so AuthContext re-mints it from
// the refresh cookie via /auth/refresh on mount.

let accessToken: string | null = null

// Legacy localStorage keys from when tokens were (insecurely) persisted in JS.
// Purged on clear() so browsers upgrading from the old version don't keep them.
const LEGACY_ACCESS_KEY = 'nc.access_token'
const LEGACY_REFRESH_KEY = 'nc.refresh_token'

export const tokenStore = {
  getAccess: (): string | null => accessToken,

  set(access: string) {
    accessToken = access
  },

  clear() {
    accessToken = null
    localStorage.removeItem(LEGACY_ACCESS_KEY)
    localStorage.removeItem(LEGACY_REFRESH_KEY)
  },
}
