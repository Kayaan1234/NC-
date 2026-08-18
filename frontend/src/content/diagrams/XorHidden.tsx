// Figure 16 — XOR before and after the hidden layer, side by side.
//
// This is the payoff for step0's XorBoundary figure, and it is drawn to be laid
// over it: same axes convention, same markers (filled = 1, hollow = 0), same
// HALO trick for text sitting on a line. What changes is the right-hand panel,
// where the four points have been moved by a hidden layer and a straight line
// finally works.
//
// The hidden weights are HAND-PICKED, not trained, and the caption says so. What
// matters is that every number downstream of them is computed here: the four
// images come from the real Math.tanh through the real z = xW + b, and the
// separating line is derived from those images rather than drawn where it looks
// about right. Pick the weights, and the picture follows whether it flatters
// them or not.

import { boundary, scale, type PlotArea } from './plot'

const PANEL = { w: 214, h: 208 }
const PAD = { top: 26, right: 22, bottom: 40, left: 40 }

const AREA_IN: PlotArea = {
  width: PANEL.w,
  height: PANEL.h,
  padding: PAD,
  xMin: -0.42,
  xMax: 1.5,
  yMin: -0.42,
  yMax: 1.5,
}

// tanh saturates, so the images crowd towards the corners of [-1, 1]. A little
// room past 1 keeps a marker at 0.9999 off the frame.
const AREA_HID: PlotArea = {
  width: PANEL.w,
  height: PANEL.h,
  padding: PAD,
  xMin: -1.45,
  xMax: 1.45,
  yMin: -1.45,
  yMax: 1.45,
}

const sIn = scale(AREA_IN)
const sHid = scale(AREA_HID)

// make_xor() from backend/services/Step1/main.cpp: class 1 means "xor is 1".
const POINTS = [
  { x: 0, y: 0, label: 0 },
  { x: 0, y: 1, label: 1 },
  { x: 1, y: 0, label: 1 },
  { x: 1, y: 1, label: 0 },
]

// One hidden layer, fan_in 2 and fan_out 2, in exactly the shapes layer.hpp
// holds them: weight is (fan_in × fan_out) read row by row, bias is one row of
// fan_out. Deliberately lopsided rather than symmetric in x₁ and x₂ — a
// symmetric pair sends (0,1) and (1,0) to the SAME point, which is correct and
// unreadable, because the two markers then sit on top of each other.
const WEIGHT = [
  [4.0, 2.4],
  [2.4, 4.0],
]
const BIAS = [-1.6, -5.0]

/** z = xW + b, then tanh over both cells. The layer's forward pass, in miniature. */
function hidden(p: { x: number; y: number }): { x: number; y: number } {
  const z = [0, 1].map((j) => p.x * WEIGHT[0][j] + p.y * WEIGHT[1][j] + BIAS[j])
  return { x: Math.tanh(z[0]), y: Math.tanh(z[1]) }
}

const IMAGES = POINTS.map((p) => ({ ...hidden(p), label: p.label }))

/**
 * A line that separates the images, derived rather than eyeballed.
 *
 * Take the direction joining the two class-0 images and its normal n. Both class-0
 * points sit on that line by construction, so they share one value of n·p; the
 * class-1 points give another. Putting the boundary halfway between the two is
 * the widest gap available along this direction, and returning it as (w1, w2, b)
 * lets plot.ts clip it to the frame the same way step0's boundary is clipped.
 */
function separator() {
  const zeros = IMAGES.filter((p) => p.label === 0)
  const ones = IMAGES.filter((p) => p.label === 1)
  const n = { x: -(zeros[1].y - zeros[0].y), y: zeros[1].x - zeros[0].x }
  const f = (p: { x: number; y: number }) => n.x * p.x + n.y * p.y
  const c = (f(zeros[0]) + Math.max(...ones.map(f))) / 2
  return { w1: n.x, w2: n.y, b: -c }
}

const SEP = separator()

const HALO = {
  stroke: 'var(--bg)',
  strokeWidth: 3,
  paintOrder: 'stroke' as const,
}

/** Filled for label 1, hollow for label 0 — the convention step0 set. */
function Marker({ x, y, label, r = 5 }: { x: number; y: number; label: number; r?: number }) {
  return (
    <circle
      cx={x}
      cy={y}
      r={r}
      fill={label === 1 ? 'currentColor' : 'var(--bg)'}
      stroke="currentColor"
      strokeWidth="1.5"
    />
  )
}

function Axes({
  s,
  ticks,
  xLabel,
  yLabel,
}: {
  s: ReturnType<typeof scale>
  ticks: number[]
  xLabel: string
  yLabel: string
}) {
  const x0 = s.sx(0)
  const y0 = s.sy(0)

  return (
    <g>
      <g opacity="0.75">
        <path d={`M${s.left} ${y0}H${s.right - 6}`} />
        <path d={`M${s.right - 6} ${y0}l-5 -3.5v7z`} fill="currentColor" stroke="none" />
        <path d={`M${x0} ${s.bottom}V${s.top + 6}`} />
        <path d={`M${x0} ${s.top + 6}l-3.5 5h7z`} fill="currentColor" stroke="none" />

        {ticks.map((t) => (
          <g key={t}>
            <path d={`M${s.sx(t)} ${y0}v4`} />
            <text
              x={s.sx(t)}
              y={y0 + 16}
              textAnchor="middle"
              fill="currentColor"
              opacity="0.8"
              fontSize="10"
              style={HALO}
            >
              {t}
            </text>
            <path d={`M${x0} ${s.sy(t)}h-4`} />
            <text
              x={x0 - 8}
              y={s.sy(t) + 3.5}
              textAnchor="end"
              fill="currentColor"
              opacity="0.8"
              fontSize="10"
              style={HALO}
            >
              {t}
            </text>
          </g>
        ))}
      </g>

      <text
        x={s.right}
        y={y0 + 17}
        textAnchor="end"
        fill="currentColor"
        stroke="none"
        opacity="0.8"
        style={HALO}
      >
        {xLabel}
      </text>
      <text x={x0 + 9} y={s.top + 4} fill="currentColor" stroke="none" opacity="0.8" style={HALO}>
        {yLabel}
      </text>
    </g>
  )
}

export default function XorHidden() {
  return (
    <svg
      viewBox="0 0 480 292"
      width="480"
      height="292"
      role="img"
      aria-labelledby="xor-hidden-title"
      fill="none"
      stroke="currentColor"
      vectorEffect="non-scaling-stroke"
    >
      <title id="xor-hidden-title">
        Two plots side by side. On the left, the four XOR points on axes x1 and x2, with the two
        labelled 1 on one diagonal and the two labelled 0 on the other, which no straight line can
        separate. On the right, the same four points after a two unit hidden layer with a tanh
        activation has moved them onto axes h1 and h2. The two points labelled 0 now sit at
        opposite corners with the two labelled 1 between and below them, and one straight line runs
        clean between the two classes.
      </title>

      <g fontFamily="var(--font-mono)" fontSize="11">
        <text x={115} y={22} textAnchor="middle" fill="currentColor" stroke="none" opacity="0.8">
          (a) what the layer sees
        </text>
        <text x={365} y={22} textAnchor="middle" fill="currentColor" stroke="none" opacity="0.8">
          (b) what it hands on
        </text>

        <g transform="translate(8, 30)">
          <Axes s={sIn} ticks={[1]} xLabel="x₁" yLabel="x₂" />
          {POINTS.map((p) => (
            <Marker key={`${p.x}${p.y}`} x={sIn.sx(p.x)} y={sIn.sy(p.y)} label={p.label} />
          ))}
        </g>

        <g transform="translate(258, 30)">
          <Axes s={sHid} ticks={[-1, 1]} xLabel="h₁" yLabel="h₂" />
          <path
            d={boundary(AREA_HID, sHid, SEP.w1, SEP.w2, SEP.b)}
            strokeWidth="1.6"
            opacity="0.9"
          />
          {IMAGES.map((p, i) => (
            <Marker key={i} x={sHid.sx(p.x)} y={sHid.sy(p.y)} label={p.label} />
          ))}
        </g>

        <g fontSize="10" opacity="0.7">
          <text x={240} y={262} textAnchor="middle" fill="currentColor" stroke="none">
            tanh saturates, so the four points get pushed out towards the corners
          </text>
          <text x={240} y={276} textAnchor="middle" fill="currentColor" stroke="none">
            and the output layer only ever has to draw the line in panel (b)
          </text>
        </g>
      </g>
    </svg>
  )
}
