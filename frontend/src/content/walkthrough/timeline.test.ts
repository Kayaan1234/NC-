// timeline.ts — placing a moment on the walkthrough clock.
//
// What these tests catch:
//
//   CAN catch — boundary errors. Every scene transition is a place where the
//   caption can lag the animation by one scene, and that reads as bad authoring
//   rather than as a bug, so nobody reports it. The boundary cases below are the
//   whole reason this module is pure functions instead of logic inside a hook.
//
//   CANNOT catch — whether the timings feel right. That is a judgement made by
//   watching it, not by asserting on it.
//
// Fixtures are deliberately tiny and hand-summed, so an expectation being wrong is
// visible by inspection rather than by trusting the code under test.

import { describe, expect, it } from 'vitest'

import {
  chapterAt,
  chapterStart,
  chapterTicks,
  formatTime,
  sceneAt,
  sceneStarts,
  totalDuration,
  type TimedScene,
} from './timeline'

// Starts: 0, 10, 30, 60. Total 100.
const SCENES: TimedScene[] = [
  { id: 'a', chapter: 'one', seconds: 10 },
  { id: 'b', chapter: 'one', seconds: 20 },
  { id: 'c', chapter: 'two', seconds: 30 },
  { id: 'd', chapter: 'three', seconds: 40 },
]

describe('layout', () => {
  it('derives starts by summing durations', () => {
    expect(sceneStarts(SCENES)).toEqual([0, 10, 30, 60])
  })

  it('totals the durations', () => {
    expect(totalDuration(SCENES)).toBe(100)
  })
})

describe('sceneAt', () => {
  it('starts on the first scene', () => {
    const at = sceneAt(SCENES, 0)
    expect(at.scene.id).toBe('a')
    expect(at.progress).toBe(0)
  })

  it('gives a boundary instant to the NEW scene', () => {
    // The half-open rule. t = 10 is b's first frame, not a's last: getting this
    // backwards leaves the previous caption up for one frame at every transition.
    expect(sceneAt(SCENES, 10).scene.id).toBe('b')
    expect(sceneAt(SCENES, 30).scene.id).toBe('c')
    expect(sceneAt(SCENES, 60).scene.id).toBe('d')
  })

  it('keeps the instant before a boundary on the old scene', () => {
    expect(sceneAt(SCENES, 9.999).scene.id).toBe('a')
    expect(sceneAt(SCENES, 29.999).scene.id).toBe('b')
  })

  it('never maps one instant to two scenes', () => {
    // Walk the whole timeline finely and assert the index only ever goes up.
    let previous = -1
    for (let t = 0; t <= 100; t += 0.25) {
      const { index } = sceneAt(SCENES, t)
      expect(index).toBeGreaterThanOrEqual(previous)
      previous = index
    }
  })

  it('reports progress within the scene, not the timeline', () => {
    const at = sceneAt(SCENES, 20) // 10s into b, which runs 20s
    expect(at.scene.id).toBe('b')
    expect(at.localT).toBe(10)
    expect(at.progress).toBeCloseTo(0.5)
  })

  it('pins past the end to the last scene, finished', () => {
    // Running off the end is normal — the player just stops there — so this must
    // clamp rather than throw.
    const at = sceneAt(SCENES, 500)
    expect(at.scene.id).toBe('d')
    expect(at.progress).toBe(1)
    expect(at.localT).toBe(40)
  })

  it('clamps a negative t to the first scene', () => {
    expect(sceneAt(SCENES, -5).scene.id).toBe('a')
  })

  it('treats a zero-length scene as finished rather than dividing by zero', () => {
    const degenerate: TimedScene[] = [{ id: 'z', chapter: 'one', seconds: 0 }]
    expect(sceneAt(degenerate, 0).progress).toBe(1)
  })

  it('throws on an empty timeline', () => {
    expect(() => sceneAt([], 0)).toThrow(/no scenes/)
  })
})

describe('chapters', () => {
  it('starts a chapter at its first scene', () => {
    expect(chapterStart(SCENES, 'one')).toBe(0)
    expect(chapterStart(SCENES, 'two')).toBe(30)
    expect(chapterStart(SCENES, 'three')).toBe(60)
  })

  it('throws for a chapter with no scenes', () => {
    // A rail entry that seeks nowhere is worse than a missing rail entry.
    expect(() => chapterStart(SCENES, 'four')).toThrow(/no scenes in chapter/)
  })

  it('reports the chapter playing at an instant', () => {
    expect(chapterAt(SCENES, 0)).toBe('one')
    expect(chapterAt(SCENES, 29)).toBe('one')
    expect(chapterAt(SCENES, 30)).toBe('two')
    expect(chapterAt(SCENES, 99)).toBe('three')
  })

  it('places scrub ticks as fractions of the total', () => {
    expect(chapterTicks(SCENES, [{ slug: 'one' }, { slug: 'two' }, { slug: 'three' }])).toEqual([
      { slug: 'one', at: 0 },
      { slug: 'two', at: 0.3 },
      { slug: 'three', at: 0.6 },
    ])
  })
})

describe('formatTime', () => {
  it('pads seconds', () => {
    expect(formatTime(0)).toBe('0:00')
    expect(formatTime(7)).toBe('0:07')
    expect(formatTime(67)).toBe('1:07')
    expect(formatTime(600)).toBe('10:00')
  })

  it('floors rather than rounds, so the readout never shows the next second early', () => {
    expect(formatTime(9.99)).toBe('0:09')
  })

  it('clamps negatives', () => {
    expect(formatTime(-3)).toBe('0:00')
  })
})
