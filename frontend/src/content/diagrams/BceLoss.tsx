import { curve, scale, ticks, type PlotArea } from './plot'

// The two halves of binary cross-entropy, plotted against the predicted
// probability p. Only one of them is ever active for a given sample: the y=1 term
// when the label is 1, the y=0 term when it is 0.
//
// This figure earns its place by explaining the `eps` clamp in binaryLoss(). Both
// curves go to infinity as the prediction approaches certainty about the wrong
// answer, so a p of exactly 0 or 1 produces log(0) = -inf and poisons the whole
// epoch's average. Seeing the asymptote is the argument for clamping.

const AREA: PlotArea = {
  width: 460,
  height: 270,
  padding: { top: 24, right: 30, bottom: 40, left: 52 },
  // The domain deliberately stops short of 0 and 1. -log(p) diverges at the ends,
  // and plot.ts only breaks a path on non-finite values — a finite-but-enormous
  // sample would still emit coordinates far outside the viewBox and draw a line
  // straight through the caption below.
  xMin: 0.008,
  xMax: 0.992,
  yMin: 0,
  yMax: 5,
}

const lossIfOne = (p: number) => -Math.log(p)
const lossIfZero = (p: number) => -Math.log(1 - p)

const HALO = {
  stroke: 'var(--bg)',
  strokeWidth: 3,
  paintOrder: 'stroke' as const,
}

export default function BceLoss() {
  const s = scale(AREA)

  return (
    <svg
      viewBox={`0 0 ${AREA.width} ${AREA.height}`}
      width={AREA.width}
      height={AREA.height}
      role="img"
      aria-labelledby="bce-title"
      fill="none"
      stroke="currentColor"
      vectorEffect="non-scaling-stroke"
    >
      <title id="bce-title">
        Two curves of binary cross-entropy loss against the predicted probability. The loss for a
        true label of 1 falls to zero as the prediction approaches 1 and rises without bound as it
        approaches 0; the curve for a true label of 0 is its mirror image.
      </title>

      <g fontFamily="var(--font-fig)" fontSize="12">
        {/* Axes */}
        <g className="fig-axis">
          <path d={`M${s.left} ${s.bottom}H${s.right}`} />
          <path d={`M${s.left} ${s.bottom}V${s.top + 6}`} />
          <path d={`M${s.left} ${s.top + 6}l-3.5 5h7z`} fill="currentColor" stroke="none" />
        </g>

        {/* x ticks: the predicted probability. */}
        <g className="fig-axis">
          {ticks(0, 1, 0.25).map((t) => {
            const x = s.sx(Math.min(Math.max(t, AREA.xMin), AREA.xMax))
            return (
              <g key={t}>
                <path d={`M${x} ${s.bottom}v4`} />
                <text
                  x={x}
                  y={s.bottom + 17}
                  textAnchor="middle"
                  fill="currentColor"
                  opacity="0.8"
                  style={HALO}
                >
                  {t}
                </text>
              </g>
            )
          })}
        </g>

        {/* y ticks: loss, in nats. */}
        <g className="fig-axis">
          {ticks(0, 4, 2).map((t) => (
            <g key={t}>
              <path d={`M${s.left} ${s.sy(t)}h-4`} />
              <text
                x={s.left - 9}
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

        {/* The two branches. Dashed for y=0 so they stay distinguishable without
            a second colour — the palette has none to spare. */}
        <path className="fig-warm" d={curve(AREA, s, lossIfOne)} strokeWidth="2.25" />
        <path
          className="fig-warm"
          d={curve(AREA, s, lossIfZero)}
          strokeWidth="2.25"
          strokeDasharray="5 4"
        />

        <text
          x={s.sx(0.14)}
          y={s.sy(3.5)}
          fill="currentColor"
          stroke="none"
          fontSize="11"
          style={HALO}
        >
          y = 1
        </text>
        <text
          x={s.sx(0.86)}
          y={s.sy(3.5)}
          textAnchor="end"
          fill="currentColor"
          stroke="none"
          fontSize="11"
          style={HALO}
        >
          y = 0
        </text>

        <text
          x={(s.left + s.right) / 2}
          y={AREA.height - 6}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          opacity="0.8"
        >
          predicted probability p
        </text>
        <text
          x={s.left - 34}
          y={(s.top + s.bottom) / 2}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          opacity="0.8"
          transform={`rotate(-90 ${s.left - 34} ${(s.top + s.bottom) / 2})`}
        >
          loss
        </text>
      </g>
    </svg>
  )
}
