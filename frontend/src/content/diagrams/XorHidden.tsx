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
import { smooth } from '../walkthrough/motion'

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
 * A line that separates a set of labelled points, derived rather than eyeballed.
 *
 * Take the direction joining the two class-0 points and its normal n. Both class-0
 * points sit on that line by construction, so they share one value of n·p; the
 * class-1 points give another. Putting the boundary halfway between the two is
 * the widest gap available along this direction, and returning it as (w1, w2, b)
 * lets plot.ts clip it to the frame the same way step0's boundary is clipped.
 *
 * Takes the points as an argument so the SAME rule can be run on the inputs as on
 * the images. That matters for XorTransform below: the line it draws over the
 * un-moved points is this function's honest best effort, and it gets one of the four
 * wrong, because on that arrangement every straight line does. A hand-drawn "bad
 * line" would be the author choosing to fail. This one fails on its own.
 */
function separator(points: { x: number; y: number; label: number }[]) {
  const zeros = points.filter((p) => p.label === 0)
  const ones = points.filter((p) => p.label === 1)
  const n = { x: -(zeros[1].y - zeros[0].y), y: zeros[1].x - zeros[0].x }
  const f = (p: { x: number; y: number }) => n.x * p.x + n.y * p.y
  const c = (f(zeros[0]) + Math.max(...ones.map(f))) / 2
  return { w1: n.x, w2: n.y, b: -c }
}

const SEP = separator(IMAGES)

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

// The same content as the two panels below, in one panel that moves.
//
// This is the step1 walkthrough's payoff scene, and the reason it is a single frame
// rather than a before-and-after is that the lesson is the MOTION. A hidden layer
// does not find a better line through the points where they are. It picks the points
// up and puts them somewhere a line already works, and watching them travel is the
// only way that reads as one idea rather than two pictures.
//
// manim calls this Transform. There is no new geometry here: the start positions are
// POINTS, the end positions are IMAGES, and both were already computed above by the
// real forward pass. All this adds is where each point sits partway between them.

const SEP_IN = separator(POINTS)

// Wide enough for both regimes at once, since the points travel across it. Inputs
// live in [0, 1] and tanh images crowd towards ±1, so this is AREA_HID with the top
// corner left a little roomier.
const AREA_MOVE: PlotArea = {
  width: 460,
  height: 288,
  padding: { top: 24, right: 26, bottom: 44, left: 46 },
  xMin: -1.45,
  xMax: 1.55,
  yMin: -1.45,
  yMax: 1.55,
}
const sMove = scale(AREA_MOVE)

const lerp = (a: number, b: number, t: number) => a + (b - a) * t

/**
 * Which points a boundary gets wrong.
 *
 * Which side of the line means "class 0" is not fixed: separator() builds its normal
 * from whichever two points carry label 0, and the sign of the offset depends on
 * where the class-1 points happened to land. So try both readings and keep the one
 * that gets more right, which is what any sane person does when handed a line and
 * asked whether it works.
 */
function misclassified(points: { x: number; y: number; label: number }[], sep: Sep): number[] {
  const side = (p: { x: number; y: number }) => sep.w1 * p.x + sep.w2 * p.y + sep.b
  const wrongIf = (zeroIsPositive: boolean) =>
    points.flatMap((p, i) => (side(p) > 0 !== ((p.label === 0) === zeroIsPositive) ? [i] : []))
  const a = wrongIf(true)
  const b = wrongIf(false)
  return a.length <= b.length ? a : b
}

type Sep = ReturnType<typeof separator>

// INDICES of the points the input-space line gets wrong, so the mark can follow its
// point as the point moves. One of four, and no line does better: that is what XOR
// not being linearly separable MEANS, and marking the casualty is what turns the
// claim into something a reader can see rather than something they are told.
const WRONG_IN = misclassified(POINTS, SEP_IN)

export function XorTransform({ moved = false, progress = 1 }: { moved?: boolean; progress?: number }) {
  // How far along the move we are. Finishing at 45% of the beat rather than at the
  // end leaves the reader looking at the result while the narration explains it,
  // which is the same reason writeOn has an `over`. At progress 0 this is exactly 0,
  // so the scene opens on the arrangement the previous scene closed with, and the
  // seam between the two is invisible.
  const m = moved ? smooth(progress / 0.45) : 0

  // Keyed by where the point STARTED, which is the one thing about it that does not
  // change while it moves. The input coordinates are unique across the four, and the
  // panel below keys its markers the same way.
  const at = POINTS.map((p, i) => ({
    id: `${p.x}${p.y}`,
    x: lerp(p.x, IMAGES[i].x, m),
    y: lerp(p.y, IMAGES[i].y, m),
    label: p.label,
  }))

  // Both lines are the same rule run on different points; see separator(). The one
  // over the inputs is wrong about a quarter of them, which is the whole argument.
  //
  // Interpolated rather than swapped at some threshold. Swapping made the line jump
  // partway through the move, which read as a rendering glitch and drew the eye away
  // from the points at the exact moment they were the thing to watch. The two normals
  // point the same way, so lerping the triple sweeps the line smoothly from one to
  // the other and never passes through a degenerate w1 = w2 = 0.
  const sep = {
    w1: lerp(SEP_IN.w1, SEP.w1, m),
    w2: lerp(SEP_IN.w2, SEP.w2, m),
    b: lerp(SEP_IN.b, SEP.b, m),
  }

  return (
    <svg
      viewBox={`0 0 ${AREA_MOVE.width} ${AREA_MOVE.height}`}
      width={AREA_MOVE.width}
      height={AREA_MOVE.height}
      role="img"
      aria-labelledby="xor-transform-title"
      fill="none"
      stroke="currentColor"
      vectorEffect="non-scaling-stroke"
    >
      <title id="xor-transform-title">
        {moved
          ? 'The four XOR points moving from their input positions to where a two unit tanh hidden layer sends them, after which a single straight line separates the two classes.'
          : 'The four XOR points on axes x1 and x2, with the best straight line through them. The two points labelled 1 sit on one diagonal and the two labelled 0 on the other, so the line gets one of the four wrong however it is placed.'}
      </title>

      <g fontFamily="var(--font-fig)" fontSize="12">
        <g className="fig-axis">
          <Axes s={sMove} ticks={[-1, 1]} xLabel="" yLabel="" />
          {/* The axis names cross-fade, because the axes genuinely change meaning
              as the points move: they arrive as the layer's inputs and leave as its
              outputs. Two labels swapping is the cheapest way to say that. */}
          <text
            x={sMove.right}
            y={sMove.sy(0) + 17}
            textAnchor="end"
            fill="currentColor"
            stroke="none"
            opacity={0.8 * (1 - m)}
            style={HALO}
          >
            x₁
          </text>
          <text
            x={sMove.right}
            y={sMove.sy(0) + 17}
            textAnchor="end"
            fill="currentColor"
            stroke="none"
            opacity={0.8 * m}
            style={HALO}
          >
            h₁
          </text>
          <text
            x={sMove.sx(0) + 9}
            y={sMove.top + 4}
            fill="currentColor"
            stroke="none"
            opacity={0.8 * (1 - m)}
            style={HALO}
          >
            x₂
          </text>
          <text
            x={sMove.sx(0) + 9}
            y={sMove.top + 4}
            fill="currentColor"
            stroke="none"
            opacity={0.8 * m}
            style={HALO}
          >
            h₂
          </text>
        </g>

        <path
          className="fig-accent"
          d={boundary(AREA_MOVE, sMove, sep.w1, sep.w2, sep.b)}
          strokeWidth="1.6"
        />

        {/* A ring round whatever the input-space line gets wrong, which fades out as
            the points move and the line stops getting anything wrong. Warm, because
            warm means error everywhere else on the site. This is the payoff in one
            mark: the reader sees the failure lift rather than being told it did. */}
        <g className="fig-warm" opacity={1 - m}>
          {WRONG_IN.map((i) => (
            <circle
              key={at[i].id}
              cx={sMove.sx(at[i].x)}
              cy={sMove.sy(at[i].y)}
              r="10"
              strokeWidth="1.5"
            />
          ))}
        </g>

        <g className="fig-subject">
          {at.map((p) => (
            <Marker key={p.id} x={sMove.sx(p.x)} y={sMove.sy(p.y)} label={p.label} />
          ))}
        </g>

        <text
          x={AREA_MOVE.width / 2}
          y={AREA_MOVE.height - 10}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          fontSize="10"
          opacity="0.7"
        >
          {moved ? 'after z = xW + b and a tanh' : 'the best line available, and it still gets one wrong'}
        </text>
      </g>
    </svg>
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

      <g fontFamily="var(--font-fig)" fontSize="12">
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
