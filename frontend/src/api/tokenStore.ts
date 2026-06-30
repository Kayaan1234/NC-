// --- Token storage ---------------------------------------------------------
//
// SECURITY NOTE (surfaced to the developer, not a silent decision):
// The backend returns the refresh token in the JSON login response body, so an
// httpOnly cookie is NOT available without backend changes (Set-Cookie + CSRF
// handling). Within this frontend slice the realistic choice is therefore
// localStorage vs in-memory only. We use localStorage so the session survives a
// page reload. Tradeoff: tokens are readable by any JS, so an XSS bug exposes
// them. The hardened path (httpOnly, SameSite cookie for the refresh token) is
// a backend change to make later.

const ACCESS_KEY = 'nc.access_token'
const REFRESH_KEY = 'nc.refresh_token'

export const tokenStore = {
  getAccess: (): string | null => localStorage.getItem(ACCESS_KEY),
  getRefresh: (): string | null => localStorage.getItem(REFRESH_KEY),

  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },

  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}
