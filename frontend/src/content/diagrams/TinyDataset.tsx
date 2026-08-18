import { boundary, scale, ticksNoZero, type PlotArea } from './plot'

// The `tiny` dataset with the boundary the neuron actually finds.
//
// The weights are not invented and not eyeballed: they are what the real Node from
// logistic_regression.hpp converges to on make_tiny() after the driver's default
// 500 epochs at lr 0.5 with seed 42 — the same run `nn --dataset tiny` performs,
// which reports 100% accuracy and a final loss of 0.0016. So the line drawn here is
// the line the reader gets if they press the button, not a plausible-looking one.
//
// Class is marked by fill, matching Xor.tsx: filled = 1, hollow = 0.

const W1 = 3.479215
const W2 = 1.910716
const B = 0.255828

const AREA: PlotArea = {
  width: 300,
  height: 260,
  padding: { top: 24, right: 26, bottom: 40, left: 46 },
  xMin: -2,
  xMax: 3,
  yMin: -2.6,
  yMax: 2.6,
}

// make_tiny() from backend/services/Step0/main.cpp, verbatim.
//
// `dx`/`dy` place each coordinate label by hand rather than by a single rule.
// A uniform up-and-right offset put (2, -0.5)'s label straight through the x₁
// axis label, which is what the far-right point's label always does — three
// points is few enough to just say where each one goes.
const POINTS = [
  { x: 1.0, y: 2.0, label: 1, dx: 10, dy: -8, anchor: 'start' as const },
  { x: -1.0, y: -1.5, label: 0, dx: 10, dy: -8, anchor: 'start' as const },
  { x: 2.0, y: -0.5, label: 1, dx: -10, dy: 17, anchor: 'end' as const },
]

const PANEL_X = 316

const HALO = {
  stroke: 'var(--bg)',
  strokeWidth: 3,
  paintOrder: 'stroke' as const,
}

export default function TinyDataset() {
  const s = scale(AREA)
  const x0 = s.sx(0)
  const y0 = s.sy(0)

  return (
    <svg
      viewBox="0 0 480 260"
      width="480"
      height="260"
      role="img"
      aria-labelledby="tiny-title"
      fill="none"
      stroke="currentColor"
      vectorEffect="non-scaling-stroke"
    >
      <title id="tiny-title">
        The three points of the tiny dataset on axes x1 and x2: (1, 2) and (2, -0.5) labelled 1 and
        drawn as filled dots, and (-1, -1.5) labelled 0 and drawn as a hollow dot. A straight line
        runs from upper left to lower right between them, with both filled points above it and the
        hollow point below, so all three are on the correct side. The line is the boundary
        3.48 x1 plus 1.91 x2 plus 0.26 equals zero, the weights and bias the trained neuron
        converges to.
      </title>

      <g fontFamily="var(--font-mono)" fontSize="11">
        {/* Axes through the origin: the boundary's intercept is read against them. */}
        <g opacity="0.75">
          <path d={`M${s.left} ${y0}H${s.right - 6}`} />
          <path d={`M${s.right - 6} ${y0}l-5 -3.5v7z`} fill="currentColor" stroke="none" />
          <path d={`M${x0} ${s.bottom}V${s.top + 6}`} />
          <path d={`M${x0} ${s.top + 6}l-3.5 5h7z`} fill="currentColor" stroke="none" />
        </g>

        <g opacity="0.75">
          {/* No tick at x = 2: the point (2, -0.5) sits just below the axis there
              and its marker lands exactly on where the label would print. Two
              ticks are enough to read the scale off. */}
          {ticksNoZero(-1, 1, 1).map((t) => (
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
          {ticksNoZero(-2, 2, 2).map((t) => (
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
        <text x={x0 + 10} y={s.top + 4} fill="currentColor" stroke="none" opacity="0.8" style={HALO}>
          x₂
        </text>

        {/* The separating hyperplane. Clipped to the frame by boundary() — at a
            slope of -1.82 this line leaves the top and bottom edges well inside
            the x range, and sampling the full domain would draw it through the
            caption. */}
        <path d={boundary(AREA, s, W1, W2, B)} strokeWidth="1.6" opacity="0.9" />

        {/* Both half-plane labels sit along the bottom, clear of the boundary and
            of the points' own coordinate labels: the upper-left corner that
            "predicts 0" naturally wants is exactly where the line enters the
            frame, and the upper right is where (1, 2) already is. */}
        <g opacity="0.6" fontSize="10">
          <text x={s.sx(2.4)} y={s.sy(-2.1)} textAnchor="middle" fill="currentColor" style={HALO}>
            predicts 1
          </text>
          <text x={s.sx(-1.45)} y={s.sy(-2.2)} textAnchor="middle" fill="currentColor" style={HALO}>
            predicts 0
          </text>
        </g>

        {POINTS.map((p) => (
          <g key={`${p.x}${p.y}`}>
            <circle
              cx={s.sx(p.x)}
              cy={s.sy(p.y)}
              r="5"
              fill={p.label === 1 ? 'currentColor' : 'var(--bg)'}
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <text
              x={s.sx(p.x) + p.dx}
              y={s.sy(p.y) + p.dy}
              textAnchor={p.anchor}
              fill="currentColor"
              stroke="none"
              fontSize="10"
              opacity="0.75"
              style={HALO}
            >
              ({p.x}, {p.y})
            </text>
          </g>
        ))}

        {/* The parameters that produced the line, so the picture and the numbers
            in the RESULT line are visibly the same thing. */}
        <g>
          <text x={PANEL_X} y={64} fill="currentColor" stroke="none" opacity="0.8" fontSize="10">
            500 epochs, lr 0.5
          </text>
          <path d={`M${PANEL_X} 76H${PANEL_X + 140}`} opacity="0.4" />

          <text x={PANEL_X} y={100} fill="currentColor" stroke="none">
            w = (3.48, 1.91)
          </text>
          <text x={PANEL_X} y={122} fill="currentColor" stroke="none">
            b = 0.26
          </text>

          <path d={`M${PANEL_X} 140H${PANEL_X + 140}`} opacity="0.4" />

          <text x={PANEL_X} y={164} fill="currentColor" stroke="none" opacity="0.8" fontSize="10">
            boundary: w·x + b = 0
          </text>
          <text x={PANEL_X} y={188} fill="currentColor" stroke="none">
            3.48x₁ + 1.91x₂
          </text>
          <text x={PANEL_X} y={208} fill="currentColor" stroke="none">
            {' '}+ 0.26 = 0
          </text>

          <text x={PANEL_X} y={236} fill="currentColor" stroke="none" opacity="0.8" fontSize="10">
            accuracy 100%
          </text>
        </g>
      </g>
    </svg>
  )
}
