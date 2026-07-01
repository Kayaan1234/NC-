// Mirrors the StrongPassword rules in backend/schemas/auth.py so we fail fast,
// client-side, with the same message the backend would return. Shared by every
// place that collects a new password (account reset + forgot-password reset).
export function passwordError(pw: string): string | null {
  if (pw.length < 8 || pw.length > 30) return 'Password must be 8–30 characters.'
  if (!/[A-Z]/.test(pw)) return 'Password needs at least one uppercase letter.'
  if (!/[0-9]/.test(pw)) return 'Password needs at least one digit.'
  return null
}
