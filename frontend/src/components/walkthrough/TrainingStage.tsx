import { useMemo } from 'react'

import { run, type DatasetName } from '../../demo'
import { boundary, scale, type PlotArea } from '../../content/diagrams/plot'

// Training, actually happening.
//
// The line on this plot moves because the weights moved. `demo.ts` runs the real
// Rung 0 neuron in the browser (the same forward pass, the same mean-normalised
// gradient, the same loss clamp) and hands back the model's state at every logged
// epoch; this walks that trajectory as the scene plays and draws the boundary those
// weights describe. Nothing here is a hand-drawn approximation of what training
// looks like, which is the same rule the static diagrams follow.
//
// The two datasets get different plot areas because they occupy different regions:
// `tiny` spreads across roughly [-1, 2], XOR sits in the unit square. Sharing one
// area would leave one of them as a cluster of dots in a corner.
//
// The epoch line under the plot is the log text `demo.ts` formats to match what
// Step0/main.cpp prints, so the reader sees the same output the binary would give.

const AREAS: Record<DatasetName, PlotArea> = {
  tiny: {
    width: 460,
    height: 260,
    padding: { top: 20, right: 24, bottom: 36, left: 44 },
    xMin: -2.2,
    xMax: 3,
    yMin: -2.6,
    yMax: 2.8,
  },
  xor: {
    width: 460,
    height: 260,
    padding: { top: 20, right: 24, bottom: 36, left: 44 },
    xMin: -0.6,
    xMax: 1.6,
    yMin: -0.6,
    yMax: 1.6,
  },
}

const POINTS: Record<DatasetName, { x: number; y: number; label: number }[]> = {
  // Copied from make_tiny() / make_xor() in Step0/main.cpp, same as demo.ts.
  tiny: [
    { x: 1, y: 2, label: 1 },
    { x: -1, y: -1.5, label: 0 },
    { x: 2, y: -0.5, label: 1 },
  ],
  xor: [
    { x: 0, y: 0, label: 0 },
    { x: 0, y: 1, label: 1 },
    { x: 1, y: 0, label: 1 },
    { x: 1, y: 1, label: 0 },
  ],
}

export default function TrainingStage({
  dataset,
  progress,
}: {
  dataset: DatasetName
  progress: number
}) {
  // A few thousand float operations, so it is cheap, but it must not rerun on
  // every animation frame.
  const result = useMemo(() => run(dataset), [dataset])

  // Only the epoch lines carry a trajectory worth watching; the header and RESULT
  // lines top and tail it.
  const frames = useMemo(
    () => result.lines.filter((l) => l.kind === 'epoch' || l.kind === 'final'),
    [result],
  )

  const area = AREAS[dataset]
  const s = scale(area)

  // Walk the trajectory with the scene, interpolating between logged epochs so the
  // line glides rather than stepping between ten fixed positions.
  const at = Math.min(progress, 1) * (frames.length - 1)
  const i = Math.min(Math.floor(at), frames.length - 2)
  const frac = at - i
  const a = frames[Math.max(0, i)]
  const b = frames[Math.min(frames.length - 1, i + 1)]

  const lerp = (x: number, y: number) => x + (y - x) * frac
  const w = a.w.map((v, k) => lerp(v, b.w[k]))
  const bias = lerp(a.b, b.b)

  const current = frac < 0.5 ? a : b

  return (
    <div className="training-stage">
      <svg
        viewBox={`0 0 ${area.width} ${area.height}`}
        width={area.width}
        height={area.height}
        role="img"
        aria-labelledby={`training-${dataset}-title`}
        fill="none"
        stroke="currentColor"
        vectorEffect="non-scaling-stroke"
      >
        <title id={`training-${dataset}-title`}>
          {dataset === 'tiny'
            ? 'Three points that a straight line can separate, with the neuron’s decision boundary moving into place as it trains.'
            : 'The four XOR points, with the neuron’s decision boundary shifting as it trains and never separating them.'}
        </title>

        <g fontFamily="var(--font-fig)" fontSize="12">
          {/* Axes through the origin: the reader is reading coordinates off them. */}
          <g className="fig-axis">
            <path d={`M${s.left} ${s.sy(0)}H${s.right}`} />
            <path d={`M${s.sx(0)} ${s.bottom}V${s.top}`} />
          </g>

          {/* The boundary the current weights describe, drawn only while the weights
              still describe one.

              On XOR they collapse: after 500 epochs |w| is 1.8e-5, so the logit
              varies by about 2e-5 across a plot two units wide and every prediction
              sits on 0.5. The line's angle at that point is decided entirely by
              float residue, and it renders as a confident diagonal that means
              nothing at all. Watching it shrink away and vanish is the honest
              picture, and it is what the narration is describing.

              The cutoff is where the logit stops varying enough to separate
              anything (1e-3 over this scale is a spread of ~0.002). A neuron that
              has actually fitted `tiny` reaches |w| ~ 1.5, so this can never hide a
              real boundary. */}
          {Math.hypot(w[0], w[1]) > 1e-3 && (
            <path
              className="fig-subject"
              d={boundary(area, s, w[0], w[1], bias)}
              strokeWidth="2.25"
            />
          )}

          {/* Filled for label 1, hollow for label 0, matching Xor.tsx. Class is
              carried by fill rather than by hue: the palette has none to spare. */}
          {POINTS[dataset].map((p) => (
            <circle
              key={`${p.x},${p.y}`}
              cx={s.sx(p.x)}
              cy={s.sy(p.y)}
              r={5}
              fill={p.label === 1 ? 'currentColor' : 'var(--bg)'}
              stroke="currentColor"
              strokeWidth="1.5"
            />
          ))}
        </g>
      </svg>

      {/* The log line the real binary would print at this epoch. */}
      <div className="training-stage__log">{current.text}</div>
      <div className="training-stage__weights">
        w = [{w.map((v) => v.toFixed(4)).join(', ')}] b = {bias.toFixed(4)}
      </div>
    </div>
  )
}
