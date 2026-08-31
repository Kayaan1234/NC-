// The motion vocabulary, checked against the arithmetic it claims to port.
//
// What these tests catch:
//
//   CAN catch — someone "simplifying" smooth() to the cubic smoothstep. That is
//   the likely edit, because 3t^2-2t^3 is the one everybody knows, it is shorter,
//   and it looks right in isolation. It is not what manim uses and the difference
//   is visible: the cubic has a non-zero second derivative at the endpoints, so
//   motion kicks off and snaps shut. The endpoint tests below fail on it.
//
//   CAN catch — writeOn losing its pathLength normalisation, which is what makes
//   one set of dash numbers work for paths of any length.
//
//   CANNOT catch — whether any of it looks right. These assert the curve, not the
//   choreography.

import { describe, expect, it } from 'vitest'

import { fadeIn, rushFrom, rushInto, smooth, thereAndBack, writeOn } from './motion'

describe('smooth', () => {
  it('runs from 0 to 1', () => {
    expect(smooth(0)).toBe(0)
    expect(smooth(1)).toBe(1)
  })

  it('matches manim to the digit at the quarter points', () => {
    // Hand-evaluated from t**3 * (10*s*s + 5*s*t + t*t), s = 1-t. These are exact
    // in binary floating point, so they can be compared without a tolerance.
    expect(smooth(0.25)).toBe(0.103515625)
    expect(smooth(0.5)).toBe(0.5)
    expect(smooth(0.75)).toBe(0.896484375)
  })

  it('is symmetric about the midpoint', () => {
    for (const t of [0.1, 0.25, 0.4, 0.5]) {
      expect(smooth(t) + smooth(1 - t)).toBeCloseTo(1, 12)
    }
  })

  it('is monotonically increasing', () => {
    let prev = -1
    for (let i = 0; i <= 100; i++) {
      const v = smooth(i / 100)
      expect(v).toBeGreaterThanOrEqual(prev)
      prev = v
    }
  })

  it('has a vanishing FIRST derivative at both ends', () => {
    const h = 1e-4
    expect((smooth(h) - smooth(0)) / h).toBeLessThan(1e-3)
    expect((smooth(1) - smooth(1 - h)) / h).toBeLessThan(1e-3)
  })

  it('has a vanishing SECOND derivative at both ends', () => {
    // This is the property that separates manim's quintic from the cubic
    // smoothstep, and the reason the motion has no kick. The cubic's second
    // derivative at 0 is 6, so it fails this by three orders of magnitude.
    const h = 1e-3
    const d2 = (t: number) => (smooth(t + h) - 2 * smooth(t) + smooth(t - h)) / (h * h)
    expect(Math.abs(d2(h))).toBeLessThan(0.1)
    expect(Math.abs(d2(1 - h))).toBeLessThan(0.1)
  })

  it('clamps out-of-range input rather than overshooting', () => {
    // Progress can land just outside [0,1] on the frame either side of a scene
    // boundary. Unclamped, the quintic runs away fast and a stroke would flash.
    expect(smooth(-0.5)).toBe(0)
    expect(smooth(1.5)).toBe(1)
  })
})

describe('the other rate functions', () => {
  // The two are mirror images, and which is which is easy to get backwards: they
  // are named for the motion they connect to, not for their own shape. rushInto
  // ends fast because it is rushing INTO the next thing.
  it('rushInto eases away from rest and arrives at full speed', () => {
    expect(rushInto(0)).toBeCloseTo(0, 12)
    expect(rushInto(1)).toBeCloseTo(1, 12)
    expect(rushInto(0.5)).toBeLessThan(0.5)
  })

  it('rushFrom starts at full speed and settles', () => {
    expect(rushFrom(0)).toBeCloseTo(0, 12)
    expect(rushFrom(1)).toBeCloseTo(1, 12)
    expect(rushFrom(0.5)).toBeGreaterThan(0.5)
  })

  it('makes the two exact mirrors of each other', () => {
    for (const t of [0.2, 0.5, 0.8]) {
      expect(rushInto(t)).toBeCloseTo(1 - rushFrom(1 - t), 12)
    }
  })

  it('thereAndBack returns to where it started', () => {
    expect(thereAndBack(0)).toBe(0)
    expect(thereAndBack(1)).toBe(0)
    expect(thereAndBack(0.5)).toBe(1)
  })
})

describe('writeOn', () => {
  it('normalises path length so one set of numbers fits any path', () => {
    // Without pathLength=1 the dash array would have to be the path's real length
    // in user units, which means measuring it, which means a layout read per frame.
    const w = writeOn(0.5)
    expect(w.pathLength).toBe(1)
    expect(w.strokeDasharray).toBe(1)
  })

  it('is fully drawn at the end of the scene', () => {
    expect(writeOn(1).strokeDashoffset).toBe(0)
  })

  it('never leaves the stroke invisible at rest', () => {
    // The regression this exists to prevent: the player opens paused at progress 0
    // and the rail seeks to scene starts, so progress 0 is a state a reader really
    // sits and looks at. A stroke hidden there renders a plot with axes and no
    // function, which reads as a diagram that failed to load rather than as one
    // about to be drawn.
    expect(writeOn(0).strokeDashoffset).toBeLessThanOrEqual(0.4)
  })

  it('finishes early in the scene rather than taking the whole beat', () => {
    // Drawing must be over well before the narration stops talking about the thing
    // being drawn. Anything past `over` is complete.
    expect(writeOn(0.35).strokeDashoffset).toBeCloseTo(0, 12)
    expect(writeOn(0.6).strokeDashoffset).toBe(0)
    expect(writeOn(0.9).strokeDashoffset).toBe(0)
  })

  it('is monotonic: a stroke never un-draws as the scene runs', () => {
    let prev = Infinity
    for (let i = 0; i <= 50; i++) {
      const off = writeOn(i / 50).strokeDashoffset
      expect(off).toBeLessThanOrEqual(prev)
      prev = off
    }
  })

  it('eases rather than drawing at a constant rate', () => {
    // Constant-rate drawing is the clearest tell that motion did not come from
    // manim. Halfway through the draw window the stroke is exactly halfway between
    // its floor and complete, but a quarter of the way in it is much less than a
    // quarter of the way there.
    expect(writeOn(0.175).strokeDashoffset).toBeCloseTo(0.2, 12)
    expect(writeOn(0.0875).strokeDashoffset).toBeGreaterThan(0.3)
  })

  it('takes a floor of 0 for a stroke that really should start from nothing', () => {
    expect(writeOn(0, { floor: 0 }).strokeDashoffset).toBe(1)
  })

  it('completes by the end of the scene for any window up to the full beat', () => {
    // `over` is a fraction OF the scene, so it must never exceed 1: a larger value
    // would leave the stroke permanently unfinished at the moment the scene hands
    // over to the next one, which is the one frame a reader is guaranteed to see.
    for (const over of [0.2, 0.35, 0.5, 1]) {
      expect(writeOn(1, { over }).strokeDashoffset).toBe(0)
    }
  })
})

describe('fadeIn', () => {
  it('holds at zero until its start point', () => {
    expect(fadeIn(0.1, 0.5)).toBe(0)
    expect(fadeIn(0.5, 0.5)).toBe(0)
  })

  it('reaches full opacity once its window has passed', () => {
    expect(fadeIn(0.8, 0.5, 0.25)).toBe(1)
    expect(fadeIn(1, 0.5, 0.25)).toBe(1)
  })

  it('is partway through inside its window', () => {
    const v = fadeIn(0.625, 0.5, 0.25)
    expect(v).toBeGreaterThan(0)
    expect(v).toBeLessThan(1)
  })
})
