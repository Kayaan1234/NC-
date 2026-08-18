// Figures 9–10 — the two new nonlinearities on math.hpp, each drawn with its
// derivative, because the derivative is the half the page is actually arguing
// about (how much gradient survives a layer).
//
// Both are sampled through plot.ts rather than drawn: tanh's derivative really
// does peak at exactly 1.0 and sigmoid's at exactly 0.25, and the whole point of
// Figure 9 is the ratio between those two numbers. A path drawn by eye would
// make that comparison a decoration instead of evidence.
//
// One file, two exports, as in MatrixOps.tsx: they share the axis furniture
// below, and split apart the first one to move would leave the other behind.
//
// currentColor only. Three curves on one pair of axes and no colour to tell them
// apart, so they are separated by dash pattern and named in a legend parked in
// the empty bottom-right quadrant.

import { curve, scale, ticks, type PlotArea, type Scale } from './plot'

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x))
const sigmoidDeriv = (x: number) => sigmoid(x) * (1 - sigmoid(x))
const tanhDeriv = (x: number) => 1 - Math.tanh(x) * Math.tanh(x)
const relu = (x: number) => Math.max(0, x)

// Knocks a hole in whatever a label sits on top of — see Sigmoid.tsx. A custom
// property has to go through `style`; it does not resolve in an SVG attribute.
//
// Two things this figure had to learn that Sigmoid.tsx never did, because there
// no curve ever crosses a label. First: a halo inside a faded group is a faded
// halo — var(--bg) at 0.75 opacity lets three quarters of the background through
// but a quarter of the curve as well, so the label still reads as struck
// through. The labels are therefore drawn at full opacity and softened with
// fill-opacity, which leaves the stroke alone. Second: 3 units of stroke is 1.5
// either side of a glyph, which does not close the gaps between characters in
// mono at this size — a dotted line shows straight through them. 5 does.
const HALO = {
  stroke: 'var(--bg)',
  strokeWidth: 5,
  paintOrder: 'stroke' as const,
}
/** Tick labels are softened here rather than by a group opacity — see HALO. */
const LABEL_FILL = 0.78

const DASH_DERIV = '5 3'
const DASH_SIGMA = '1.5 3'

/** An x axis drawn along y = 0, with an arrowhead and its ticks below it. */
function XAxis({
  s,
  at: y,
  label,
  values,
}: {
  s: Scale
  at: number
  label: string
  values: number[]
}) {
  return (
    <g>
      <g opacity="0.75">
        <path d={`M${s.left} ${y}H${s.right - 6}`} />
        <path d={`M${s.right - 6} ${y}l-5 -3.5v7z`} fill="currentColor" stroke="none" />
        {values.map((t) => (
          <path key={t} d={`M${s.sx(t)} ${y}v4`} />
        ))}
      </g>
      {values.map((t) => (
        <text
          key={t}
          x={s.sx(t)}
          y={y + 16}
          textAnchor="middle"
          fill="currentColor"
          fillOpacity={LABEL_FILL}
          style={HALO}
        >
          {t}
        </text>
      ))}
      <text
        x={s.right}
        y={y + 16}
        textAnchor="end"
        fill="currentColor"
        fillOpacity={LABEL_FILL}
        style={HALO}
      >
        {label}
      </text>
    </g>
  )
}

/** A y axis standing at x = 0, so the reader can see what is symmetric about it. */
function YAxis({ s, at: x, values }: { s: Scale; at: number; values: number[] }) {
  return (
    <g>
      <g opacity="0.75">
        <path d={`M${x} ${s.bottom}V${s.top + 6}`} />
        <path d={`M${x} ${s.top + 6}l-3.5 5h7z`} fill="currentColor" stroke="none" />
        {values.map((t) => (
          <path key={t} d={`M${x} ${s.sy(t)}h-4`} />
        ))}
      </g>
      {values.map((t) => (
        <text
          key={t}
          x={x - 8}
          y={s.sy(t) + 3.5}
          textAnchor="end"
          fill="currentColor"
          fillOpacity={LABEL_FILL}
          style={HALO}
        >
          {t}
        </text>
      ))}
    </g>
  )
}

// --- Figure 9: tanh, its derivative, and sigmoid's for scale ------------------

const TANH_AREA: PlotArea = {
  width: 460,
  height: 260,
  padding: { top: 24, right: 28, bottom: 40, left: 48 },
  xMin: -4,
  xMax: 4,
  yMin: -1.15,
  yMax: 1.15,
}

/** One legend row: a sample of the stroke, then what it is. */
function Key({
  x,
  y,
  dash,
  opacity,
  children,
}: {
  x: number
  y: number
  dash?: string
  opacity?: number
  children: string
}) {
  return (
    <g>
      <path d={`M${x} ${y - 4}h20`} strokeDasharray={dash} opacity={opacity ?? 0.9} />
      <text x={x + 26} y={y} fill="currentColor" stroke="none" fontSize="10" opacity="0.8">
        {children}
      </text>
    </g>
  )
}

export function Tanh() {
  const s = scale(TANH_AREA)
  const yZero = s.sy(0)
  const xZero = s.sx(0)

  return (
    <svg
      viewBox={`0 0 ${TANH_AREA.width} ${TANH_AREA.height}`}
      width={TANH_AREA.width}
      height={TANH_AREA.height}
      role="img"
      aria-labelledby="tanh-title"
      fill="none"
      stroke="currentColor"
      vectorEffect="non-scaling-stroke"
    >
      <title id="tanh-title">
        A plot of tanh, an S-shaped curve through the origin bounded by minus one and one, together
        with its derivative one minus tanh squared, which peaks at 1.0 at x equals zero and falls
        away to zero in both tails, and the derivative of the sigmoid, which peaks far lower at
        0.25.
      </title>

      <g fontFamily="var(--font-mono)" fontSize="11">
        {/* The two asymptotes tanh approaches but never reaches. */}
        <g opacity="0.45" strokeDasharray="3 4">
          <path d={`M${s.left} ${s.sy(1)}H${s.right}`} />
          <path d={`M${s.left} ${s.sy(-1)}H${s.right}`} />
        </g>

        {/* sigmoid's derivative first, so the two curves the page is about are
            painted over it rather than under it. */}
        <path
          d={curve(TANH_AREA, s, sigmoidDeriv)}
          strokeWidth="1.5"
          strokeDasharray={DASH_SIGMA}
          opacity="0.7"
        />
        <path d={curve(TANH_AREA, s, tanhDeriv)} strokeWidth="1.5" strokeDasharray={DASH_DERIV} />
        <path d={curve(TANH_AREA, s, Math.tanh)} strokeWidth="1.75" />

        {/* Axes AFTER the curves, unlike Sigmoid.tsx, because here a curve runs
            through a tick label: σ′ peaks at 0.25 and so passes exactly through
            the "0.25" mark. The labels carry a var(--bg) halo that knocks a hole
            in whatever is behind them, which only works if they are painted
            second. Drawn before the curves, the label reads as struck through. */}
        <XAxis s={s} at={yZero} label="x" values={ticks(-3, 3, 1).filter((t) => t !== 0)} />
        <YAxis s={s} at={xZero} values={[1, 0.25, -1]} />

        {/* The two peaks being compared: 1.0 against 0.25, both at x = 0. */}
        <circle cx={xZero} cy={s.sy(1)} r="3" fill="currentColor" stroke="none" />
        <circle cx={xZero} cy={s.sy(0.25)} r="2.5" fill="currentColor" stroke="none" opacity="0.7" />

        {/* Parked in the bottom-right quadrant, where all three curves are
            positive and nothing can collide with it. */}
        <g>
          <Key x={262} y={152}>
            tanh(x)
          </Key>
          <Key x={262} y={172} dash={DASH_DERIV}>
            1 − tanh²(x), peak 1.0
          </Key>
          <Key x={262} y={192} dash={DASH_SIGMA} opacity={0.7}>
            σ′(x), peak 0.25
          </Key>
        </g>
      </g>
    </svg>
  )
}

// --- Figure 10: ReLU and its step derivative ---------------------------------

// Two panels in one canvas, done entirely with padding: the left panel reserves
// the right-hand 268 units and the right panel reserves the left-hand 292, so
// plot.ts's scale() places both without needing to know about the other.
const RELU_AREA: PlotArea = {
  width: 480,
  height: 236,
  padding: { top: 30, right: 268, bottom: 50, left: 44 },
  xMin: -3,
  xMax: 3,
  yMin: -0.25,
  yMax: 3.2,
}

const RELU_DERIV_AREA: PlotArea = {
  ...RELU_AREA,
  padding: { top: 30, right: 20, bottom: 50, left: 292 },
  yMin: -0.25,
  yMax: 1.4,
}

export function Relu() {
  const a = scale(RELU_AREA)
  const b = scale(RELU_DERIV_AREA)
  const xs = ticks(-2, 2, 1).filter((t) => t !== 0)

  return (
    <svg
      viewBox={`0 0 ${RELU_AREA.width} ${RELU_AREA.height}`}
      width={RELU_AREA.width}
      height={RELU_AREA.height}
      role="img"
      aria-labelledby="relu-title"
      fill="none"
      stroke="currentColor"
      vectorEffect="non-scaling-stroke"
    >
      <title id="relu-title">
        Two panels. On the left, ReLU: flat along zero for negative inputs, then a straight line of
        slope one for positive inputs, with a sharp kink at the origin. On the right, its
        derivative: exactly zero for inputs up to and including zero, and exactly one after that, a
        step with a filled dot at zero and an open circle above it.
      </title>

      <g fontFamily="var(--font-mono)" fontSize="11">
        {/* --- (a) relu(z) --- */}
        <text x={a.left} y={16} fill="currentColor" stroke="none" fontSize="11" opacity="0.85">
          (a) relu(z)
        </text>
        <XAxis s={a} at={a.sy(0)} label="z" values={xs} />
        <YAxis s={a} at={a.sx(0)} values={[1, 2, 3]} />
        <path d={curve(RELU_AREA, a, relu)} strokeWidth="1.75" />
        <circle cx={a.sx(0)} cy={a.sy(0)} r="3" fill="currentColor" stroke="none" />

        {/* --- (b) relu'(z) --- */}
        <text x={b.left} y={16} fill="currentColor" stroke="none" fontSize="11" opacity="0.85">
          (b) relu′(z)
        </text>
        <XAxis s={b} at={b.sy(0)} label="z" values={xs} />
        <YAxis s={b} at={b.sx(0)} values={[1]} />

        {/* Drawn as two segments, not sampled: the jump at z = 0 is the whole
            content of the panel, and curve() would join the two levels with a
            vertical line straight through it — drawing a value the function
            never takes. */}
        <path d={`M${b.left} ${b.sy(0)}H${b.sx(0)}`} strokeWidth="1.75" />
        <path d={`M${b.sx(0)} ${b.sy(1)}H${b.right - 10}`} strokeWidth="1.75" />
        {/* Closed at z = 0, open just above it: relu_deriv(0) returns 0. */}
        <circle cx={b.sx(0)} cy={b.sy(0)} r="3" fill="currentColor" stroke="none" />
        <circle cx={b.sx(0)} cy={b.sy(1)} r="3" fill="var(--bg)" strokeWidth="1.25" />

        <text
          x={a.left + (a.right - a.left) / 2}
          y={222}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          fontSize="10"
          opacity="0.7"
        >
          no exponential — one comparison
        </text>
        <text
          x={b.left + (b.right - b.left) / 2}
          y={222}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          fontSize="10"
          opacity="0.7"
        >
          0 or 1, never in between
        </text>
      </g>
    </svg>
  )
}
