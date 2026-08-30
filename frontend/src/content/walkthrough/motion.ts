// The motion vocabulary, ported from manim.
//
// 3Blue1Brown's animations are built from a small set of named gestures, and the
// two that matter here are `smooth` (how anything eases) and `ShowCreation` (a
// stroke drawing itself on). This module is those two, as pure functions.
//
// Pure on purpose, and separate from React on purpose: the same reasoning as
// timeline.ts. Easing and reveal are arithmetic, they are the kind of thing that
// is worth a test, and neither needs a component to be correct.
//
// Nothing here uses @keyframes or the Web Animations API. The walkthrough already
// has a requestAnimationFrame clock (components/walkthrough/useTimeline.ts) that
// re-renders from state, and every function below is a way of turning that clock's
// `progress` into an SVG attribute. Motion stays a function of time rather than
// something a stylesheet owns, which is what makes it seekable.

/** Clamp to the unit interval. Progress can arrive slightly out of range on the
 *  frame either side of a scene boundary. */
const unit = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t)

/**
 * manim's default rate function, from manimlib/utils/rate_functions.py:
 *
 *     def smooth(t):
 *         s = 1 - t
 *         return (t**3) * (10 * s * s + 5 * s * t + t * t)
 *
 * The quintic smoothstep. Its first AND second derivatives are zero at both ends,
 * which is the reason manim uses it over the more familiar cubic 3t^2-2t^3: with
 * the second derivative vanishing too, motion has no perceptible kick at the start
 * or snap at the finish. Everything in a 3B1B video eases this way by default, so
 * matching it is most of what makes borrowed motion feel borrowed correctly.
 */
export function smooth(t: number): number {
  const x = unit(t)
  const s = 1 - x
  return x ** 3 * (10 * s * s + 5 * s * x + x * x)
}

/**
 * manim's `rush_into`: the accelerating half of `smooth`, so it eases away from
 * rest and arrives at full speed. Rushing INTO whatever comes next. Use it when
 * the next scene continues this motion rather than starting a new one.
 */
export function rushInto(t: number): number {
  return 2 * smooth(0.5 * unit(t))
}

/**
 * manim's `rush_from`: the decelerating half, so it starts at full speed and
 * settles. Coming FROM a motion already under way, the mirror of rushInto.
 */
export function rushFrom(t: number): number {
  return 2 * smooth(0.5 * (unit(t) + 1)) - 1
}

/**
 * manim's `there_and_back`: out and back within one span. What `Indicate` uses,
 * and what a value that should be drawn attention to and then left alone wants.
 */
export function thereAndBack(t: number): number {
  const x = unit(t)
  return smooth(x < 0.5 ? 2 * x : 2 * (1 - x))
}

/**
 * ShowCreation: a stroke drawing itself on, left to right.
 *
 * Spread onto any SVG <path>, <circle> or <line>:
 *
 *     <path d={curve(...)} {...writeOn(p)} />
 *
 * The trick is `pathLength={1}`, which tells the renderer to report this path's
 * length as 1 whatever its actual geometry. Dash lengths are then fractions of the
 * path rather than user units, so one dash of length 1 covers exactly the whole
 * stroke and an offset of 1 hides exactly all of it. No measuring, no getTotalLength,
 * no layout read, and the same three numbers work for a 40px tick and a 900px curve.
 *
 * Progress is eased through `smooth`, so the line accelerates away and settles
 * rather than crawling at a constant rate. Constant-rate drawing is the single
 * clearest tell that an animation was not made in manim.
 *
 * ---- Why it does not start from nothing ----
 *
 * `floor` and `over` exist for the same reason Neuron.tsx's opacity FLOOR does,
 * and they were added for the same reason: watching it fail.
 *
 * The player opens paused, and the rail seeks. Both land the viewer at a scene
 * start, where progress is 0. A bare draw-on there renders a plot with axes, tick
 * labels, an asymptote and no function, which does not read as "about to be
 * drawn". It reads as a diagram that failed to load.
 *
 * So the stroke is never less than `floor` of itself, and it finishes within the
 * first `over` of the scene rather than taking the whole beat. Together those mean
 * the resting state is always a recognisable curve, and the drawing is over well
 * before the narration stops talking about it. The default `over` is 0.35, the
 * same fraction Neuron.tsx fades over, because two different arrival rates in one
 * frame read as one of them lagging.
 */
export function writeOn(progress: number, { floor = 0.6, over = 0.35 } = {}) {
  const drawn = floor + (1 - floor) * smooth(unit(progress) / over)
  return {
    pathLength: 1,
    strokeDasharray: 1,
    strokeDashoffset: 1 - drawn,
  }
}

/**
 * FadeIn, for things that should not be drawn stroke-first.
 *
 * Text is the case that matters. Running `writeOn` over a glyph reveals it sliced
 * down the middle, which reads as a rendering fault rather than as writing; manim
 * fades text in for the same reason. `at` delays the fade so a label can arrive
 * after the thing it labels, which is the ordering nearly every 3B1B shot uses.
 */
export function fadeIn(progress: number, at = 0, over = 0.25): number {
  if (over <= 0) return progress >= at ? 1 : 0
  return smooth((unit(progress) - at) / over)
}
