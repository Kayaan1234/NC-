// A multilayer perceptron: two inputs, one hidden layer of three units, two
// outputs. Drawn in the same register as Neuron.tsx — circles, straight edges,
// no fills — because this figure is that one repeated, and the reader is meant
// to map the two onto each other.
//
// The σ sits *inside* each hidden unit rather than in a box of its own (as it
// does in Neuron.tsx, where there is only one of them). With twelve edges on the
// canvas, three more boxes would be the noisiest thing in the picture, and the
// point the prose needs — the nonlinearity lives in the hidden layer — reads
// just as well from the glyph in the circle.
//
// Biases are deliberately not drawn. Every hidden and output unit has one, but
// five more stub nodes would bury the connection pattern, which is what this
// figure is actually for; the caption says so instead.
//
// Strokes and labels are currentColor throughout, so the figure takes its colour
// from the prose around it.

const R = 16
const INPUT = { x: 78, ys: [96, 168] }
const HIDDEN = { x: 240, ys: [56, 132, 208] }
const OUTPUT = { x: 402, ys: [96, 168] }
const LABEL_Y = 250

/**
 * Endpoints of the segment between two circles, trimmed to their circumferences.
 *
 * Deliberately a copy of the helper in Neuron.tsx rather than a shared import:
 * it is six lines, and the two figures are free to diverge (this one is all
 * uniform radii, that one is not) without either being refactored around the
 * other.
 */
function edge(
  a: { x: number; y: number },
  b: { x: number; y: number },
): { x1: number; y1: number; x2: number; y2: number } {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len
  return {
    x1: a.x + ux * R,
    y1: a.y + uy * R,
    x2: b.x - ux * R,
    y2: b.y - uy * R,
  }
}

/** Every unit of one layer to every unit of the next — the "fully connected" bit. */
function Edges({
  from,
  to,
}: {
  from: { x: number; ys: number[] }
  to: { x: number; ys: number[] }
}) {
  // Dimmed to 0.75, as Xor.tsx dims its axes: twelve edges at full strength
  // out-shout the seven units they connect, and the units are the subject.
  return (
    <g opacity="0.75">
      {from.ys.map((ay) =>
        to.ys.map((by) => {
          const e = edge({ x: from.x, y: ay }, { x: to.x, y: by })
          return (
            <path
              key={`${ay}-${by}`}
              d={`M${e.x1} ${e.y1}L${e.x2} ${e.y2}`}
              markerEnd="url(#mlp-arrow)"
            />
          )
        }),
      )}
    </g>
  )
}

function Unit({
  x,
  y,
  label,
  fontSize = 12,
}: {
  x: number
  y: number
  label: string
  fontSize?: number
}) {
  return (
    <g>
      <circle cx={x} cy={y} r={R} />
      <text
        x={x}
        y={y + fontSize * 0.36}
        textAnchor="middle"
        fill="currentColor"
        stroke="none"
        fontSize={fontSize}
      >
        {label}
      </text>
    </g>
  )
}

export default function Mlp() {
  return (
    <svg
      viewBox="0 0 480 264"
      width="480"
      height="264"
      role="img"
      aria-labelledby="mlp-title"
      fill="none"
      stroke="currentColor"
      strokeOpacity="0.85"
      vectorEffect="non-scaling-stroke"
    >
      <title id="mlp-title">
        A multilayer perceptron with three layers of units: an input layer of two, a hidden layer
        of three, and an output layer of two. Every unit is joined to every unit of the next layer,
        giving six connections into the hidden layer and six out of it. Each hidden unit is marked
        with a sigma for the sigmoid applied to its sum.
      </title>

      <defs>
        <marker
          id="mlp-arrow"
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
        {/* Edges first, so the units are drawn over the ends of their own lines. */}
        <Edges from={INPUT} to={HIDDEN} />
        <Edges from={HIDDEN} to={OUTPUT} />

        {INPUT.ys.map((y, i) => (
          <Unit key={y} x={INPUT.x} y={y} label={`x${'₁₂'[i]}`} />
        ))}

        {/* σ inside the unit: the sum happens here and is squashed here. */}
        {HIDDEN.ys.map((y) => (
          <Unit key={y} x={HIDDEN.x} y={y} label="σ" fontSize={15} />
        ))}

        {OUTPUT.ys.map((y, i) => (
          <Unit key={y} x={OUTPUT.x} y={y} label={`ŷ${'₁₂'[i]}`} fontSize={11} />
        ))}

        {/* Layer names, so the prose can talk about "the hidden layer" and the
            reader knows which column that is. */}
        <g fontSize="11" opacity="0.7">
          {[
            { x: INPUT.x, text: 'input' },
            { x: HIDDEN.x, text: 'hidden' },
            { x: OUTPUT.x, text: 'output' },
          ].map((l) => (
            <text
              key={l.text}
              x={l.x}
              y={LABEL_Y}
              textAnchor="middle"
              fill="currentColor"
              stroke="none"
            >
              {l.text}
            </text>
          ))}
        </g>
      </g>
    </svg>
  )
}
