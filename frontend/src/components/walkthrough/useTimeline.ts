import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

// The walkthrough's clock.
//
// This is the one deliberate departure from the house animation rule. tokens.css
// says the entire animation budget is colour transitions and that no @keyframes
// exist anywhere, and that still holds: nothing here adds a stylesheet animation,
// and every moving thing on screen is still state being re-rendered. What changes is
// the pacing mechanism. NeuronDemo.tsx advances a line counter on a setInterval,
// which is right for a log that types itself, but a timeline has to be scrubbed and
// sought to an arbitrary second, so it needs frame-accurate time rather than ticks.
// Hence requestAnimationFrame.
//
// Two things this gets right that the earlier setInterval version of the same idea
// got wrong (see the note in NeuronDemo.tsx, which documents the bug it caused):
//
//   1. The stop condition lives in the frame callback, never inside a setState
//      updater. React is free to call an updater twice, and it does under
//      StrictMode, so a side effect in there runs twice too.
//   2. The frame id is a local of the effect, and the cleanup cancels that exact
//      frame. StrictMode mounts, unmounts and remounts, so a loop that outlived its
//      cleanup would leave two loops advancing the same clock and the walkthrough
//      would play at double speed. That looks like bad authoring rather than a bug,
//      which is why it is worth being careful about.
//
// `externalClock` is the seam for narration audio. Supply a function returning the
// current time of an <audio> element and the timeline follows it instead of
// accumulating its own; nothing else in the walkthrough has to change. Nothing
// supplies one today.

export interface TimelineControls {
  /** Elapsed seconds. */
  t: number
  playing: boolean
  rate: number
  play: () => void
  pause: () => void
  toggle: () => void
  seek: (seconds: number) => void
  setRate: (rate: number) => void
  /** True once the clock has reached the end. */
  finished: boolean
}

export function useTimeline(
  total: number,
  options: { externalClock?: () => number } = {},
): TimelineControls {
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [rate, setRate] = useState(1)

  // The clock's authoritative value. State is for rendering; this is what the frame
  // callback reads and writes, so a render never has to have landed for the next
  // frame to be correct.
  const tRef = useRef(0)
  // Read inside the loop so changing speed does not tear the loop down and restart
  // it, which would drop a frame and lose the accumulated sub-frame remainder.
  const rateRef = useRef(rate)
  const externalClock = options.externalClock
  const externalRef = useRef(externalClock)

  // Layout rather than passive, because both of these are read inside a
  // requestAnimationFrame callback. A passive effect is flushed after paint, so a
  // frame that was already scheduled can run first and read the stale value; a
  // layout effect lands in the same task as the commit, ahead of the next frame.
  //
  // Worth being clear that the stakes here are small: `rate` lagging one commit
  // would be imperceptible, and `externalClock` is undefined in every current
  // caller. Nothing in this file is load-bearing on effect timing. Layout is simply
  // the correct choice of the two, and writing a ref during render is the thing
  // being avoided, since React may call a component body without committing it.
  useLayoutEffect(() => {
    rateRef.current = rate
    externalRef.current = externalClock
  }, [rate, externalClock])

  const seek = useCallback(
    (seconds: number) => {
      const clamped = Math.min(Math.max(0, seconds), total)
      tRef.current = clamped
      setT(clamped)
    },
    [total],
  )

  const play = useCallback(() => {
    // Pressing play at the end restarts rather than doing nothing, which is what a
    // video player does and what a reader who wants a second look expects.
    if (tRef.current >= total) {
      tRef.current = 0
      setT(0)
    }
    setPlaying(true)
  }, [total])

  const pause = useCallback(() => setPlaying(false), [])
  const toggle = useCallback(() => {
    if (playing) pause()
    else play()
  }, [playing, pause, play])

  useEffect(() => {
    if (!playing || total <= 0) return

    let frame = 0
    let last = performance.now()

    const tick = (now: number) => {
      const external = externalRef.current
      let next: number

      if (external) {
        next = external()
      } else {
        // Delta time rather than a frame count: a dropped frame or a background
        // tab must not make the walkthrough run slow, it should skip ahead.
        const dt = (now - last) / 1000
        next = tRef.current + dt * rateRef.current
      }
      last = now

      if (next >= total) {
        tRef.current = total
        setT(total)
        setPlaying(false)
        return // deliberately no further frame
      }

      tRef.current = next
      setT(next)
      frame = requestAnimationFrame(tick)
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing, total])

  return {
    t,
    playing,
    rate,
    play,
    pause,
    toggle,
    seek,
    setRate,
    finished: t >= total && total > 0,
  }
}
