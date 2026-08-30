// The walkthrough clock, as pure arithmetic. No React, no DOM, no rendering.
//
// Everything the player shows at a given moment — which scene, which chapter, how
// far through, where the chapter ticks sit on the scrub bar — is derived here from
// one number: elapsed seconds. Keeping that derivation in plain functions is what
// makes it testable without mounting a component, and it is the part that has to be
// exactly right: an off-by-one at a scene boundary shows the wrong caption beside
// the right animation, which reads as an authoring mistake rather than a bug.
//
// Scenes carry a DURATION, never an absolute start time. Start times are derived by
// summing. Storing both would mean an edit to one scene's length silently desyncs
// every scene after it, and nothing would catch it.

/** The minimum a scene needs for the clock to place it. */
export interface TimedScene {
  id: string
  chapter: string
  seconds: number
}

/** Cumulative start time of each scene, in seconds. Parallel to `scenes`. */
export function sceneStarts(scenes: readonly TimedScene[]): number[] {
  const starts: number[] = []
  let acc = 0
  for (const scene of scenes) {
    starts.push(acc)
    acc += scene.seconds
  }
  return starts
}

export function totalDuration(scenes: readonly TimedScene[]): number {
  return scenes.reduce((sum, s) => sum + s.seconds, 0)
}

export interface SceneAt<T> {
  scene: T
  index: number
  /** Seconds elapsed within this scene. */
  localT: number
  /** 0 at the scene's first frame, 1 at its last. Drives stage animation. */
  progress: number
}

/**
 * Which scene is on screen at `t` seconds.
 *
 * Intervals are half-open — `[start, start + seconds)` — so a `t` landing exactly on
 * a boundary belongs to the NEW scene, and no `t` ever maps to two scenes. `t` past
 * the end pins to the last scene at progress 1 rather than throwing, because the
 * clock reaching the end is normal and the player just stops there.
 */
export function sceneAt<T extends TimedScene>(scenes: readonly T[], t: number): SceneAt<T> {
  if (scenes.length === 0) throw new Error('sceneAt: no scenes')

  const clamped = Math.max(0, t)
  const starts = sceneStarts(scenes)

  for (let i = scenes.length - 1; i >= 0; i--) {
    if (clamped >= starts[i]) {
      const scene = scenes[i]
      const localT = Math.min(clamped - starts[i], scene.seconds)
      return {
        scene,
        index: i,
        localT,
        // A zero-length scene would divide by zero; treat it as finished.
        progress: scene.seconds > 0 ? Math.min(1, localT / scene.seconds) : 1,
      }
    }
  }

  // Unreachable while starts[0] === 0, but a negative t must still land somewhere.
  return { scene: scenes[0], index: 0, localT: 0, progress: 0 }
}

/**
 * When a chapter begins, in seconds. This is what a rail click seeks to, and what a
 * /learn/:slug deep link resolves to.
 */
export function chapterStart(scenes: readonly TimedScene[], chapter: string): number {
  const starts = sceneStarts(scenes)
  const index = scenes.findIndex((s) => s.chapter === chapter)
  if (index === -1) throw new Error(`chapterStart: no scenes in chapter ${JSON.stringify(chapter)}`)
  return starts[index]
}

/** Which chapter is playing at `t`. Drives the rail's current-item marker. */
export function chapterAt(scenes: readonly TimedScene[], t: number): string {
  return sceneAt(scenes, t).scene.chapter
}

/**
 * Chapter boundaries as fractions of the total, for the scrub bar's tick marks.
 * Fractions rather than seconds so the bar can be laid out in percentages and stay
 * correct at any width.
 */
export function chapterTicks(
  scenes: readonly TimedScene[],
  chapters: readonly { slug: string }[],
): { slug: string; at: number }[] {
  const total = totalDuration(scenes)
  if (total === 0) return []
  return chapters.map((c) => ({ slug: c.slug, at: chapterStart(scenes, c.slug) / total }))
}

/** `2:07`, for the transport's elapsed/total readout. */
export function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds))
  const m = Math.floor(whole / 60)
  const s = whole % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}
