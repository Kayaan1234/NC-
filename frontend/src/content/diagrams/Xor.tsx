import { boundary, scale, type PlotArea } from './plot'

// XOR at the two stages the prose needs it: the four points on their own, then the
// best straight line anyone can draw through them.
//
// Two named exports from one file rather than the usual one-default-per-file,
// because the second figure IS the first with a line added — the reader maps one
// onto the other, so the axes, the scale and the four points have to be the same
// objects. Split across two files they would drift the first time either moved.
//
// Class is marked by fill, never by hue: filled = 1, hollow = 0. BceLoss.tsx spends
// a dash pattern rather than a second colour for the same reason (the palette has
// none to spare), and LearningRate.tsx already uses a var(--bg)-filled dot to mean
// "a different kind of point".

const AREA: PlotArea = {
  width: 254,
  height: 252,
  padding: { top: 26, right: 24, bottom: 44, left: 46 },
  // A little breathing room past the unit square on all sides, so a marker at
  // (1, 1) is not cut in half by the frame.
  xMin: -0.42,
  xMax: 1.5,
  yMin: -0.42,
  yMax: 1.5,
}

// make_xor() from backend/services/Step0/main.cpp, verbatim.
const POINTS = [
  { x: 0, y: 0, label: 0 },
  { x: 0, y: 1, label: 1 },
  { x: 1, y: 0, label: 1 },
  { x: 1, y: 1, label: 0 },
]

// The 3-of-4 line: w = (1, 1), b = -0.5, i.e. x₁ + x₂ = 0.5. It cuts (0,0) away
// from the other three, which is the most any straight line can get right here —
// separate one corner and the two it leaves behind carry different labels.
const W1 = 1
const W2 = 1
const B = -0.5

const predict = (p: { x: number; y: number }) => (W1 * p.x + W2 * p.y + B > 0 ? 1 : 0)

const HALO = {
  stroke: 'var(--bg)',
  strokeWidth: 3,
  paintOrder: 'stroke' as const,
}

const s = scale(AREA)

/** Filled for label 1, hollow for label 0. */
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

/** The shared plot: axes, ticks at 0 and 1, and the four points. */
function Plot() {
  const x0 = s.sx(0)
  const y0 = s.sy(0)

  return (
    <g>
      {/* Axes through the origin, since the data is the unit square and the
          reader is reading coordinates off them. */}
      <g opacity="0.75">
        <path d={`M${s.left} ${y0}H${s.right - 6}`} />
        <path d={`M${s.right - 6} ${y0}l-5 -3.5v7z`} fill="currentColor" stroke="none" />
        <path d={`M${x0} ${s.bottom}V${s.top + 6}`} />
        <path d={`M${x0} ${s.top + 6}l-3.5 5h7z`} fill="currentColor" stroke="none" />
      </g>

      {/* Ticks at 0 and 1 only: those are the only values XOR takes. */}
      <g opacity="0.75">
        {[0, 1].map((t) => (
          <g key={`x${t}`}>
            <path d={`M${s.sx(t)} ${y0}v4`} />
            <text
              x={s.sx(t)}
              y={y0 + 17}
              textAnchor="middle"
              fill="currentColor"
              opacity="0.8"
              style={HALO}
            >
              {t}
            </text>
          </g>
        ))}
        {[1].map((t) => (
          <g key={`y${t}`}>
            <path d={`M${x0} ${s.sy(t)}h-4`} />
            <text
              x={x0 - 9}
              y={s.sy(t) + 3.5}
              textAnchor="end"
              fill="currentColor"
              opacity="0.8"
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
        x₁
      </text>
      <text
        x={x0 + 10}
        y={s.top + 4}
        fill="currentColor"
        stroke="none"
        opacity="0.8"
        style={HALO}
      >
        x₂
      </text>

      {POINTS.map((p) => (
        <Marker key={`${p.x}${p.y}`} x={s.sx(p.x)} y={s.sy(p.y)} label={p.label} />
      ))}
    </g>
  )
}

/** ● y = 1  ○ y = 0, drawn with the same markers the plot uses. */
function Legend({ x, y }: { x: number; y: number }) {
  return (
    <g opacity="0.85">
      <Marker x={x + 5} y={y - 4} label={1} r={4} />
      <text x={x + 16} y={y} fill="currentColor" stroke="none" fontSize="10">
        y = 1
      </text>
      <Marker x={x + 74} y={y - 4} label={0} r={4} />
      <text x={x + 85} y={y} fill="currentColor" stroke="none" fontSize="10">
        y = 0
      </text>
    </g>
  )
}

function Frame({ title, id, children }: { title: string; id: string; children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 480 252"
      width="480"
      height="252"
      role="img"
      aria-labelledby={id}
      fill="none"
      stroke="currentColor"
      vectorEffect="non-scaling-stroke"
    >
      <title id={id}>{title}</title>
      <g fontFamily="var(--font-mono)" fontSize="11">
        <Plot />
        {children}
      </g>
    </svg>
  )
}

// --- Figure: the data --------------------------------------------------------

const TABLE_X = 292
const ROW_Y = [94, 118, 142, 166]

/**
 * The four XOR points, with the truth table they come from beside them.
 *
 * The table is drawn inside the SVG rather than written as a Markdown table
 * because nothing in prose.css styles `<table>` — a Markdown one renders as bare
 * unstyled rows. Keeping it here also puts each row's marker next to its label, so
 * the table and the plot read as one object.
 */
export function XorPoints() {
  return (
    <Frame
      id="xor-points-title"
      title="The four XOR points plotted on axes x1 and x2, beside the truth table they come from.
        (0,0) has label 0, (0,1) has label 1, (1,0) has label 1, and (1,1) has label 0. Points
        labelled 1 are drawn as filled dots and points labelled 0 as hollow dots, so the two
        labelled 1 sit on one diagonal and the two labelled 0 on the other."
    >
      <g>
        <g opacity="0.8">
          <text x={TABLE_X} y={68} fill="currentColor" stroke="none">
            x₁
          </text>
          <text x={TABLE_X + 40} y={68} fill="currentColor" stroke="none">
            x₂
          </text>
          <text x={TABLE_X + 92} y={68} fill="currentColor" stroke="none">
            y
          </text>
        </g>
        <path d={`M${TABLE_X} 76H${TABLE_X + 132}`} opacity="0.4" />

        {POINTS.map((p, i) => (
          <g key={`${p.x}${p.y}`}>
            <text x={TABLE_X} y={ROW_Y[i]} fill="currentColor" stroke="none" opacity="0.9">
              {p.x}
            </text>
            <text x={TABLE_X + 40} y={ROW_Y[i]} fill="currentColor" stroke="none" opacity="0.9">
              {p.y}
            </text>
            <text x={TABLE_X + 92} y={ROW_Y[i]} fill="currentColor" stroke="none" opacity="0.9">
              {p.label}
            </text>
            <Marker x={TABLE_X + 120} y={ROW_Y[i] - 4} label={p.label} r={4} />
          </g>
        ))}

        <Legend x={TABLE_X} y={212} />
      </g>
    </Frame>
  )
}

// --- Figure: the best a line can do ------------------------------------------

/**
 * The same four points with x₁ + x₂ = 0.5 drawn through them, and the verdict on
 * each — three right, one wrong.
 */
export function XorBoundary() {
  const wrong = POINTS.find((p) => predict(p) !== p.label)!

  return (
    <Frame
      id="xor-boundary-title"
      title="The same four XOR points with the straight line x1 + x2 = 0.5 drawn across them. The
        line cuts the point (0,0) away from the other three. It classifies (0,0), (0,1) and (1,0)
        correctly but gets (1,1) wrong, which is ringed: three of four, or 75 percent, and no
        straight line can do better."
    >
      <g>
        <path d={boundary(AREA, s, W1, W2, B)} strokeWidth="1.6" opacity="0.9" />

        {/* The line, named. A "predicts 0" label in the lower-left landed on top
            of the origin's own tick label — the corner it wants is the corner the
            axes already occupy — and the tally on the right says which side each
            point came down on anyway. */}
        <text
          x={s.sx(0.95)}
          y={s.sy(0.58)}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          fontSize="10"
          opacity="0.75"
          style={HALO}
        >
          x₁ + x₂ = 0.5
        </text>

        {/* Ring the one it cannot get right. */}
        <circle
          cx={s.sx(wrong.x)}
          cy={s.sy(wrong.y)}
          r="10.5"
          strokeDasharray="3 3"
          strokeWidth="1.25"
          opacity="0.9"
        />

        {/* The tally, so "75%" is read off the four rows rather than asserted. */}
        <g>
          <text x={TABLE_X} y={68} fill="currentColor" stroke="none" opacity="0.8">
            y
          </text>
          <text x={TABLE_X + 32} y={68} fill="currentColor" stroke="none" opacity="0.8">
            pred
          </text>
          <path d={`M${TABLE_X} 76H${TABLE_X + 132}`} opacity="0.4" />

          {POINTS.map((p, i) => {
            const got = predict(p)
            const ok = got === p.label
            return (
              <g key={`${p.x}${p.y}`} opacity={ok ? 0.9 : 1}>
                <Marker x={TABLE_X + 5} y={ROW_Y[i] - 4} label={p.label} r={4} />
                <text x={TABLE_X + 40} y={ROW_Y[i]} fill="currentColor" stroke="none">
                  {got}
                </text>
                <text x={TABLE_X + 74} y={ROW_Y[i]} fill="currentColor" stroke="none">
                  {ok ? 'ok' : 'wrong'}
                </text>
              </g>
            )
          })}

          <path d={`M${TABLE_X} 186H${TABLE_X + 132}`} opacity="0.4" />
          <text x={TABLE_X} y={208} fill="currentColor" stroke="none">
            3 of 4 — 75%
          </text>
        </g>
      </g>
    </Frame>
  )
}
