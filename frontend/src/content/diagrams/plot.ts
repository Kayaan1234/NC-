// Coordinate mapping for function plots on the learn pages.
//
// The point of this file is that a curve on a maths page should be the function,
// not a drawing of it. Sampling f(x) and mapping the result into SVG user space
// gives a sigmoid whose inflection really is at (0, 0.5) and whose asymptotes are
// really flat — where a hand-drawn path is only ever approximately right, and
// stays wrong forever. It also means the next plot (tanh, ReLU, a loss curve)
// costs one line.

export type PlotArea = {
  /** SVG canvas size, in user units. */
  width: number
  height: number
  /** Padding inside the canvas, leaving room for axis labels. */
  padding: { top: number; right: number; bottom: number; left: number }
  /** The slice of the function's domain and range that is drawn. */
  xMin: number
  xMax: number
  yMin: number
  yMax: number
}

export type Scale = {
  /** Maths x → SVG x. */
  sx: (x: number) => number
  /** Maths y → SVG y. Inverted, because SVG's y axis points down. */
  sy: (y: number) => number
  /** SVG coordinates of the plot rectangle's edges. */
  left: number
  right: number
  top: number
  bottom: number
}

export function scale(area: PlotArea): Scale {
  const { width, height, padding, xMin, xMax, yMin, yMax } = area
  const left = padding.left
  const right = width - padding.right
  const top = padding.top
  const bottom = height - padding.bottom
  return {
    sx: (x) => left + ((x - xMin) / (xMax - xMin)) * (right - left),
    sy: (y) => bottom - ((y - yMin) / (yMax - yMin)) * (bottom - top),
    left,
    right,
    top,
    bottom,
  }
}

/**
 * Sample `f` across the domain and return an SVG path `d`.
 *
 * `samples` is the number of line segments; 160 is smooth at any size a figure
 * is displayed at, and keeps the emitted path small enough to read in the DOM.
 * Non-finite results (a function with a pole in range) break the path rather
 * than drawing a spurious vertical line across the plot.
 */
export function curve(area: PlotArea, s: Scale, f: (x: number) => number, samples = 160): string {
  const step = (area.xMax - area.xMin) / samples
  let d = ''
  let penDown = false
  for (let i = 0; i <= samples; i++) {
    const x = area.xMin + i * step
    const y = f(x)
    if (!Number.isFinite(y)) {
      penDown = false
      continue
    }
    d += `${penDown ? 'L' : 'M'}${round(s.sx(x))} ${round(s.sy(y))}`
    penDown = true
  }
  return d
}

/**
 * The visible part of a decision boundary `w1·x + w2·y + b = 0`, as an SVG path.
 *
 * NOT `curve()` with the line rearranged as y = mx + c. `curve()` samples the whole
 * domain and only breaks the path on non-finite values, so any boundary steeper
 * than the plot's aspect ratio emits coordinates far outside the viewBox and draws
 * straight through the caption beneath — and a vertical boundary (w2 = 0) has no
 * y = mx + c form at all. Intersecting the frame instead handles both, and returns
 * '' when the line misses the visible rectangle entirely.
 */
export function boundary(area: PlotArea, s: Scale, w1: number, w2: number, b: number): string {
  const { xMin, xMax, yMin, yMax } = area
  const eps = 1e-9
  const hits: { x: number; y: number }[] = []
  const push = (x: number, y: number) => {
    if (x >= xMin - eps && x <= xMax + eps && y >= yMin - eps && y <= yMax + eps) hits.push({ x, y })
  }
  // Where the line crosses each of the four edges. A near-zero weight means the
  // line is parallel to that pair of edges and never crosses them.
  if (Math.abs(w2) > eps) {
    push(xMin, -(w1 * xMin + b) / w2)
    push(xMax, -(w1 * xMax + b) / w2)
  }
  if (Math.abs(w1) > eps) {
    push(-(w2 * yMin + b) / w1, yMin)
    push(-(w2 * yMax + b) / w1, yMax)
  }
  // A line through a corner is found twice, once from each edge meeting there.
  const ends = hits.filter(
    (p, i) => hits.findIndex((q) => Math.hypot(q.x - p.x, q.y - p.y) < 1e-6) === i,
  )
  if (ends.length < 2) return ''

  // Two edge crossings is the usual case; take the farthest-apart pair so a
  // grazing corner hit can't shorten the segment to nothing.
  let [a, c] = ends
  let longest = -1
  for (let i = 0; i < ends.length; i++) {
    for (let j = i + 1; j < ends.length; j++) {
      const d = Math.hypot(ends[i].x - ends[j].x, ends[i].y - ends[j].y)
      if (d > longest) {
        longest = d
        a = ends[i]
        c = ends[j]
      }
    }
  }
  return `M${round(s.sx(a.x))} ${round(s.sy(a.y))}L${round(s.sx(c.x))} ${round(s.sy(c.y))}`
}

/** Evenly spaced tick values from `from` to `to` inclusive. */
export function ticks(from: number, to: number, step: number): number[] {
  const out: number[] = []
  // Half a step of slack so floating-point drift can't drop the final tick.
  for (let v = from; v <= to + step / 2; v += step) out.push(Number(v.toFixed(6)))
  return out
}

/**
 * Ticks with the origin dropped.
 *
 * Every figure with crossed axes wants this: a "0" label at the origin collides
 * with the other axis it is labelling, and both axes would print it. Each plot
 * used to re-derive it with its own `.filter((t) => t !== 0)` on the call site.
 */
export function ticksNoZero(from: number, to: number, step: number): number[] {
  const out: number[] = []
  for (let v = from; v <= to + step / 2; v += step) {
    const t = Number(v.toFixed(6))
    if (t !== 0) out.push(t)
  }
  return out
}

function round(n: number): number {
  return Math.round(n * 100) / 100
}
