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

/** Evenly spaced tick values from `from` to `to` inclusive. */
export function ticks(from: number, to: number, step: number): number[] {
  const out: number[] = []
  // Half a step of slack so floating-point drift can't drop the final tick.
  for (let v = from; v <= to + step / 2; v += step) out.push(Number(v.toFixed(6)))
  return out
}

function round(n: number): number {
  return Math.round(n * 100) / 100
}
