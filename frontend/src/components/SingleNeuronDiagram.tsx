import { useMemo } from 'react'

/**
 * The thesis of Rung 0, drawn literally: one neuron with four inputs and one
 * output. Cyan signal particles flow along the four dendrites into the soma
 * (the site's "forward pass" language), the cell body pulses as it fires, and a
 * single activation leaves down the axon. Inside the soma sits the sigmoid glyph
 * — the activation function this rung is about. Respects reduced-motion by
 * dropping the travelling particles and showing a lit static frame.
 *
 * SVG + <animateMotion> (matching RoadmapNeuron) rather than canvas: the labels
 * (x₁…x₄, weights, the z/σ caption) need to stay crisp and selectable.
 */

interface Pt {
  x: number
  y: number
}

const SOMA: Pt & { r: number } = { x: 366, y: 192, r: 54 }
const OUT: Pt & { r: number } = { x: 606, y: 192, r: 22 }

const INPUTS: Array<Pt & { x_label: string; w_label: string }> = [
  { x: 98, y: 66, x_label: 'x₁', w_label: 'w₁' },
  { x: 98, y: 150, x_label: 'x₂', w_label: 'w₂' },
  { x: 98, y: 234, x_label: 'x₃', w_label: 'w₃' },
  { x: 98, y: 318, x_label: 'x₄', w_label: 'w₄' },
]

/** Cubic with horizontal tangents, so a dendrite reads as a flowing fibre rather
 *  than a straight wire. */
function edgePath(a: Pt, b: Pt): string {
  const dx = (b.x - a.x) * 0.5
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`
}

// A small sigmoid drawn through the soma centre — the activation function.
const SIGMOID = `M ${SOMA.x - 30} ${SOMA.y + 15} C ${SOMA.x - 12} ${SOMA.y + 15}, ${SOMA.x - 13} ${SOMA.y}, ${SOMA.x} ${SOMA.y} C ${SOMA.x + 13} ${SOMA.y}, ${SOMA.x + 12} ${SOMA.y - 15}, ${SOMA.x + 30} ${SOMA.y - 15}`

export default function SingleNeuronDiagram() {
  const reduced = useMemo(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  )

  const axonId = 'snd-axon'

  return (
    <figure className="snd card">
      <svg
        className="snd-svg"
        viewBox="0 0 700 384"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="A single neuron: four weighted inputs feed a cell body that applies a sigmoid activation and emits one output."
      >
        <defs>
          <radialGradient id="snd-halo">
            <stop offset="0%" stopColor="rgba(45,226,230,0.5)" />
            <stop offset="100%" stopColor="rgba(45,226,230,0)" />
          </radialGradient>
        </defs>

        {/* dendrites (input edges) */}
        <g className="snd-edges">
          {INPUTS.map((inp, i) => (
            <path key={i} id={`snd-in-${i}`} className="snd-edge" d={edgePath(inp, SOMA)} />
          ))}
          <path id={axonId} className="snd-edge" d={edgePath(SOMA, OUT)} />
        </g>

        {/* travelling signals — omitted under reduced-motion */}
        {!reduced && (
          <g className="snd-signals">
            {INPUTS.map((_, i) => (
              <circle key={i} className="snd-signal" r={3.4}>
                <animateMotion
                  dur={`${2.2 + (i % 4) * 0.28}s`}
                  begin={`${i * 0.22}s`}
                  repeatCount="indefinite"
                >
                  <mpath href={`#snd-in-${i}`} />
                </animateMotion>
              </circle>
            ))}
            <circle className="snd-signal" data-axon="" r={4}>
              <animateMotion dur="2.1s" begin="0.9s" repeatCount="indefinite">
                <mpath href={`#${axonId}`} />
              </animateMotion>
            </circle>
          </g>
        )}

        {/* input nodes */}
        <g className="snd-inputs">
          {INPUTS.map((inp, i) => (
            <g key={i} transform={`translate(${inp.x} ${inp.y})`}>
              <circle className="snd-halo-node" r={22} fill="url(#snd-halo)" />
              <circle className="snd-in-core" r={13} />
              <text className="snd-io mono" dy="0.34em">
                {inp.x_label}
              </text>
              <text className="snd-w mono" x={(SOMA.x - inp.x) * 0.34} y={(SOMA.y - inp.y) * 0.34 - 8}>
                {inp.w_label}
              </text>
            </g>
          ))}
        </g>

        {/* soma */}
        <g transform={`translate(${SOMA.x} ${SOMA.y})`}>
          <circle className="snd-halo-node" r={SOMA.r * 1.7} fill="url(#snd-halo)" />
          {!reduced && <circle className="snd-pulse" r={SOMA.r + 8} />}
          <circle className="snd-soma" r={SOMA.r} />
        </g>
        <path className="snd-sigmoid" d={SIGMOID} />
        <text className="snd-soma-label mono" x={SOMA.x} y={SOMA.y - SOMA.r - 12}>
          soma
        </text>

        {/* output */}
        <g className="snd-out-arbor" aria-hidden="true">
          {[-16, 0, 16].map((dy, i) => (
            <path
              key={i}
              className="snd-edge"
              d={`M ${OUT.x + OUT.r} ${OUT.y} C ${OUT.x + OUT.r + 14} ${OUT.y}, ${OUT.x + OUT.r + 18} ${OUT.y + dy}, ${OUT.x + OUT.r + 30} ${OUT.y + dy}`}
            />
          ))}
        </g>
        <g transform={`translate(${OUT.x} ${OUT.y})`}>
          <circle className="snd-halo-node" r={34} fill="url(#snd-halo)" />
          <circle className="snd-out-core" r={OUT.r} />
          <text className="snd-io mono" dy="0.34em">
            {'ŷ'}
          </text>
        </g>
      </svg>

      <figcaption className="snd-cap mono" aria-hidden="true">
        <span>
          z = <b>&Sigma;</b>&#7522; w&#7522;x&#7522; + b
        </span>
        <span className="snd-arrow">&rarr;</span>
        <span>
          a = <b>&sigma;</b>(z)
        </span>
      </figcaption>
    </figure>
  )
}
