import { curve, scale, type PlotArea } from './plot'

// Gradient descent on a toy loss surface at two badly-chosen learning rates.
//
// The page's closing paragraph names exactly two failure modes — too low and the
// model takes forever, too high and it overshoots the minimum — so the figure
// shows those two and nothing else. Both panels descend the same parabola from
// the same kind of start; only `lr` differs.
//
// The steps are computed, not drawn. For L(w) = w², dL/dw = 2w, so the update
// w ← w − lr·2w is just multiplication by (1 − 2·lr). That factor is 0.88 on the
// left (creeping toward zero) and −1.1 on the right (flipping sign and growing),
// which is the whole story in one number.

const LOSS = (w: number) => w * w

const panel = (left: number, right: number): PlotArea => ({
  width: 480,
  height: 250,
  padding: { top: 30, right, bottom: 46, left },
  xMin: -2,
  xMax: 2,
  yMin: 0,
  yMax: 4,
})

const TOO_SMALL = panel(44, 266)
const TOO_LARGE = panel(266, 44)

/** Successive w values under w ← w(1 − 2·lr). */
function descent(w0: number, lr: number, steps: number): number[] {
  const factor = 1 - 2 * lr
  const out = [w0]
  for (let i = 0; i < steps; i++) out.push(out[out.length - 1] * factor)
  return out
}

const HALO = {
  stroke: 'var(--bg)',
  strokeWidth: 3,
  paintOrder: 'stroke' as const,
}

function Panel({ area, ws, label }: { area: PlotArea; ws: number[]; label: string }) {
  const s = scale(area)
  // Clip the walk to what the panel can actually show, so a diverging run stops
  // at the frame instead of drawing across the neighbouring panel.
  const visible = ws.filter((w) => w >= area.xMin && w <= area.xMax && LOSS(w) <= area.yMax)
  const points = visible.map((w) => ({ x: s.sx(w), y: s.sy(LOSS(w)) }))

  return (
    <g>
      {/* The loss surface. */}
      <path d={curve(area, s, LOSS)} strokeWidth="1.5" opacity="0.55" />

      {/* Axis along the bottom: the weight being tuned. */}
      <g opacity="0.7">
        <path d={`M${s.left} ${s.bottom}H${s.right}`} />
        <path d={`M${s.sx(0)} ${s.bottom}v4`} />
        <text
          x={s.sx(0)}
          y={s.bottom + 17}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          fontSize="10"
          opacity="0.8"
          style={HALO}
        >
          w*
        </text>
      </g>

      {/* The walk: dashed connectors, then a dot at each visited weight. */}
      <path
        d={points.map((p, i) => `${i ? 'L' : 'M'}${p.x} ${p.y}`).join('')}
        strokeDasharray="3 3"
        strokeWidth="1.25"
        opacity="0.8"
      />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r={i === 0 ? 3.5 : 2.5}
          fill={i === 0 ? 'var(--bg)' : 'currentColor'}
          stroke="currentColor"
          strokeWidth="1.25"
        />
      ))}

      <text
        x={(s.left + s.right) / 2}
        y={area.height - 8}
        textAnchor="middle"
        fill="currentColor"
        stroke="none"
        fontSize="11"
        opacity="0.85"
      >
        {label}
      </text>
    </g>
  )
}

export default function LearningRate() {
  return (
    <svg
      viewBox="0 0 480 250"
      width="480"
      height="250"
      role="img"
      aria-labelledby="lr-title"
      fill="none"
      stroke="currentColor"
      vectorEffect="non-scaling-stroke"
    >
      <title id="lr-title">
        Two panels showing gradient descent on the same parabolic loss curve. On the left a small
        learning rate takes many shrinking steps and is still far from the minimum; on the right a
        large learning rate overshoots the minimum each time and lands further away than it started.
      </title>
      <g fontFamily="var(--font-mono)">
        <Panel area={TOO_SMALL} ws={descent(1.8, 0.06, 6)} label="lr too small, creeps" />
        <Panel area={TOO_LARGE} ws={descent(0.35, 1.05, 6)} label="lr too large, overshoots" />
      </g>
    </svg>
  )
}
