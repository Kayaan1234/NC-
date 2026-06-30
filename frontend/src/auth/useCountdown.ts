import { useEffect, useState } from 'react'

/** Counts `seconds` down to 0, ticking every second. Pass 0/undefined for idle.
 *  Used to lock the resend/change buttons for the backend's Retry-After window. */
export function useCountdown(): {
  remaining: number
  start: (seconds: number) => void
} {
  const [remaining, setRemaining] = useState(0)

  useEffect(() => {
    if (remaining <= 0) return
    const id = setInterval(() => {
      setRemaining((s) => (s <= 1 ? 0 : s - 1))
    }, 1000)
    return () => clearInterval(id)
  }, [remaining])

  return { remaining, start: setRemaining }
}

/** "2m 05s" / "45s" for a countdown label. */
export function formatCountdown(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  if (m > 0) return `${m}m ${String(s).padStart(2, '0')}s`
  return `${s}s`
}
