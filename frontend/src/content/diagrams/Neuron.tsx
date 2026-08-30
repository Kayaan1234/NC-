// A single neuron: four inputs, weighted and summed with a bias, through a
// nonlinearity, to one output. This is the picture the whole course is built on,
// so it's drawn plainly — circles, straight edges, one box — in the register of a
// figure in a textbook rather than an illustration.
//
// Edge endpoints are computed from the node geometry instead of being eyeballed,
// so every line meets its circle exactly on the circumference and stays correct if
// a node moves. Strokes and labels are currentColor throughout: the figure takes
// its colour from the prose around it, and no token change can leave it invisible.
//
// The step0 walkthrough builds this up a piece at a time rather than showing it
// whole, so the parts are grouped by the stage at which they arrive. `reveal`
// defaults to 'all', which renders exactly what this file rendered before the
// walkthrough existed, so any page importing it as a plain figure is unaffected.
//
// Ordering note: the summation circle arrives WITH the weighted edges, not with the
// Σ glyph. Edges have to point at something, and four arrows converging on empty
// space reads as a mistake. The 'sum' stage then fills the circle it is pointing at.

export type NeuronReveal = 'inputs' | 'weights' | 'sum' | 'bias' | 'sigmoid' | 'all'

const ORDER: NeuronReveal[] = ['inputs', 'weights', 'sum', 'bias', 'sigmoid', 'all']

/**
 * Parts at or below the current stage are solid; the part arriving now fades in
 * across the first part of the scene. Opacity from a prop, never a keyframe: the
 * codebase has none, and motion here is state being re-rendered like everywhere else.
 */
function opacityFor(at: NeuronReveal, reveal: NeuronReveal, progress: number): number {
  const current = ORDER.indexOf(reveal)
  const mine = ORDER.indexOf(at)
  if (mine < current) return 1
  if (mine > current) return 0
  // The arriving piece fades up over the first third of the beat, from a floor
  // rather than from nothing. A true zero looked like a bug: the player opens
  // paused at t = 0, where progress is also 0, so the whole stage was blank until
  // someone pressed play.
  const FLOOR = 0.3
  return FLOOR + (1 - FLOOR) * Math.min(1, progress / 0.35)
}

const INPUT_X = 62
const INPUT_R = 14
const INPUT_YS = [42, 96, 150, 204]
const SUM = { x: 252, y: 123, r: 26 }
const BIAS = { x: 252, y: 236, r: 14 }

/** Endpoints of the segment between two circles, trimmed to their circumferences. */
function edge(
  a: { x: number; y: number; r: number },
  b: { x: number; y: number; r: number },
): { x1: number; y1: number; x2: number; y2: number } {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len
  return {
    x1: a.x + ux * a.r,
    y1: a.y + uy * a.r,
    x2: b.x - ux * b.r,
    y2: b.y - uy * b.r,
  }
}

export default function Neuron({
  reveal = 'all',
  progress = 1,
}: {
  reveal?: NeuronReveal
  progress?: number
} = {}) {
  const o = (at: NeuronReveal) => opacityFor(at, reveal, progress)

  return (
    <svg
      viewBox="0 0 480 280"
      width="480"
      height="280"
      role="img"
      aria-labelledby="neuron-title"
      fill="none"
      stroke="currentColor"
      strokeOpacity="0.85"
      vectorEffect="non-scaling-stroke"
    >
      <title id="neuron-title">
        Four inputs x1 to x4, each multiplied by a weight w1 to w4, feeding into a summation node
        that also takes a bias b. The sum passes through a sigmoid and produces one output, y-hat.
      </title>

      <defs>
        <marker
          id="nc-arrow"
          viewBox="0 0 8 8"
          refX="7"
          refY="4"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M0 0.5L7.5 4L0 7.5z" fill="currentColor" stroke="none" />
        </marker>
      </defs>

      <g fontFamily="var(--font-mono)" fontSize="12" strokeWidth="1.25">
        {/* Inputs, and the weighted edges into the summation node. */}
        {INPUT_YS.map((y, i) => {
          const e = edge({ x: INPUT_X, y, r: INPUT_R }, SUM)
          // Label each weight partway along its own edge, nudged clear of it.
          const t = 0.46
          const lx = e.x1 + (e.x2 - e.x1) * t
          const ly = e.y1 + (e.y2 - e.y1) * t - 7
          return (
            <g key={y}>
              <g opacity={o('inputs')}>
                <circle cx={INPUT_X} cy={y} r={INPUT_R} />
                <text
                  x={INPUT_X}
                  y={y + 4}
                  textAnchor="middle"
                  fill="currentColor"
                  stroke="none"
                >
                  x{'₁₂₃₄'[i]}
                </text>
              </g>
              <g opacity={o('weights')}>
                <path
                  d={`M${e.x1} ${e.y1}L${e.x2} ${e.y2}`}
                  markerEnd="url(#nc-arrow)"
                />
                <text
                  x={lx}
                  y={ly}
                  textAnchor="middle"
                  fill="currentColor"
                  stroke="none"
                  fontSize="11"
                  opacity="0.75"
                >
                  w{'₁₂₃₄'[i]}
                </text>
              </g>
            </g>
          )
        })}

        {/* Bias, entering the sum from below — it is added like any other term,
            it just has no input to be weighted against. */}
        <g opacity={o('bias')}>
          <circle cx={BIAS.x} cy={BIAS.y} r={BIAS.r} />
          <text x={BIAS.x} y={BIAS.y + 4} textAnchor="middle" fill="currentColor" stroke="none">
            b
          </text>
          {(() => {
            const e = edge(BIAS, SUM)
            return <path d={`M${e.x1} ${e.y1}L${e.x2} ${e.y2}`} markerEnd="url(#nc-arrow)" />
          })()}
        </g>

        {/* Summation. The circle arrives with the edges that point into it; the
            glyph arrives when the prose gets to the sum itself. */}
        <circle cx={SUM.x} cy={SUM.y} r={SUM.r} opacity={o('weights')} />
        <text
          x={SUM.x}
          y={SUM.y + 6}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          fontSize="17"
          opacity={o('sum')}
        >
          Σ
        </text>

        {/* The nonlinearity, boxed rather than circled so it reads as a different
            kind of thing from the arithmetic nodes. */}
        <g opacity={o('sigmoid')}>
          <path d={`M${SUM.x + SUM.r} ${SUM.y}H${332}`} markerEnd="url(#nc-arrow)" />
          <rect x="340" y="101" width="58" height="44" rx="2" />
          <text x="369" y="129" textAnchor="middle" fill="currentColor" stroke="none" fontSize="16">
            σ
          </text>
        </g>

        {/* Output. */}
        <g opacity={o('all')}>
          <path d={`M398 ${SUM.y}H${438}`} markerEnd="url(#nc-arrow)" />
          <text x="452" y="128" textAnchor="middle" fill="currentColor" stroke="none">
            ŷ
          </text>
        </g>
      </g>
    </svg>
  )
}
