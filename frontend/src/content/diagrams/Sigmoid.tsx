import { curve, scale, ticksNoZero, type PlotArea } from './plot'

// σ(x) = 1 / (1 + e^-x), plotted rather than drawn — see plot.ts.
//
// Textbook conventions, deliberately: axes with arrowheads, ticks outside the
// frame, dashed asymptotes at y=0 and y=1, and the inflection at (0, ½) marked
// because that is where the derivative peaks at 0.25, which is the point the
// surrounding prose is making about vanishing gradients.
//
// Every stroke is currentColor and every label fills with currentColor, so the
// figure takes its colour from the prose it sits in. Nothing here hardcodes a
// hex value: changing --text must not be able to leave a diagram invisible.

const AREA: PlotArea = {
  width: 460,
  height: 260,
  padding: { top: 24, right: 28, bottom: 40, left: 48 },
  xMin: -8,
  xMax: 8,
  yMin: 0,
  yMax: 1,
}

const sigma = (x: number) => 1 / (1 + Math.exp(-x))

// Tick labels sit on top of the lines they annotate — the "1" lands directly on
// the dashed asymptote. Painting a background-coloured stroke behind the glyphs
// knocks a hole in whatever runs underneath, which is what a printed figure does
// by breaking the rule. `var(--bg)` has to go through `style` rather than a
// presentation attribute: custom properties don't resolve in SVG attributes.
const HALO = {
  stroke: 'var(--bg)',
  strokeWidth: 3,
  paintOrder: 'stroke' as const,
}

/**
 * `tangent` adds the line through the inflection with slope 0.25, for the beat of
 * the step0 walkthrough that talks about the derivative. Off by default, so the
 * figure renders exactly as it did before the walkthrough existed.
 */
export default function Sigmoid({ tangent = false }: { tangent?: boolean } = {}) {
  const s = scale(AREA)
  const yZero = s.sy(0)
  const yOne = s.sy(1)
  const yHalf = s.sy(0.5)
  const xZero = s.sx(0)

  return (
    <svg
      viewBox={`0 0 ${AREA.width} ${AREA.height}`}
      width={AREA.width}
      height={AREA.height}
      role="img"
      aria-labelledby="sigmoid-title"
      fill="none"
      stroke="currentColor"
      vectorEffect="non-scaling-stroke"
    >
      <title id="sigmoid-title">
        A plot of the logistic sigmoid, rising from an asymptote at y equals zero to an asymptote
        at y equals one, passing through the point (0, 0.5).
      </title>

      <g fontFamily="var(--font-mono)" fontSize="11">
        {/* The upper asymptote. There is no dashed line at y=0 because the x axis
            already is y=0 — drawing both would put a dashed line underneath a
            solid one. */}
        <g opacity="0.45" strokeDasharray="3 4">
          <path d={`M${s.left} ${yOne}H${s.right}`} />
        </g>

        {/* Axes. The y axis sits at x=0 rather than at the frame's left edge,
            because the function is symmetric about it and the reader needs to see
            that. */}
        <g opacity="0.75">
          <path d={`M${s.left} ${yZero}H${s.right - 6}`} />
          <path d={`M${s.right - 6} ${yZero}l-5 -3.5v7z`} fill="currentColor" stroke="none" />
          <path d={`M${xZero} ${s.bottom}V${s.top + 6}`} />
          <path d={`M${xZero} ${s.top + 6}l-3.5 5h7z`} fill="currentColor" stroke="none" />
        </g>

        {/* x ticks stop at ±6 while the axis runs to ±8: the last stretch of the
            axis is left bare so the arrowhead and the "x" label have room, and a
            tick at 8 would otherwise sit underneath the label. Skipping 0 too —
            the axes already cross there and the y axis carries that label. */}
        <g opacity="0.75">
          {ticksNoZero(-6, 6, 2).map((t) => (
            <g key={t}>
              <path d={`M${s.sx(t)} ${yZero}v4`} />
              <text
                x={s.sx(t)}
                y={yZero + 17}
                textAnchor="middle"
                fill="currentColor"
                opacity="0.8"
                style={HALO}
              >
                {t}
              </text>
            </g>
          ))}
        </g>

        {/* y ticks at the two values that matter: the upper bound and the
            midpoint. 0 is omitted — its label would sit on the origin, colliding
            with the x axis it labels. */}
        <g opacity="0.75">
          {[0.5, 1].map((t) => (
            <g key={t}>
              <path d={`M${xZero} ${s.sy(t)}h-4`} />
              <text
                x={xZero - 9}
                y={s.sy(t) + 3.5}
                textAnchor="end"
                fill="currentColor"
                opacity="0.8"
                style={HALO}
              >
                {t === 0.5 ? '0.5' : t}
              </text>
            </g>
          ))}
        </g>

        {/* The curve itself. */}
        <path d={curve(AREA, s, sigma)} strokeWidth="1.75" />

        {/* The tangent at the inflection, drawn only when the prose is on the
            derivative. Its slope IS 0.25, computed from the same scale as the
            curve rather than eyeballed, so the claim in the narration is something
            the reader can check against the axes. */}
        {tangent && (
          <g opacity="0.7">
            {(() => {
              // y = 0.25x + 0.5, clipped to a span either side of the origin that
              // stays inside the plot's y range.
              const span = 1.7
              const at = (x: number) => 0.25 * x + 0.5
              return (
                <path
                  d={`M${s.sx(-span)} ${s.sy(at(-span))}L${s.sx(span)} ${s.sy(at(span))}`}
                  strokeDasharray="4 3"
                  strokeWidth="1.25"
                />
              )
            })()}
            <text
              x={s.sx(2.1)}
              y={s.sy(0.5) - 8}
              fill="currentColor"
              stroke="none"
              fontSize="10"
              opacity="0.85"
              style={HALO}
            >
              slope 0.25
            </text>
          </g>
        )}

        {/* The inflection point, where σ(0) = 0.5 and the derivative is at its
            maximum of 0.25. */}
        <circle cx={xZero} cy={yHalf} r="3" fill="currentColor" stroke="none" />

        <text
          x={s.right - 4}
          y={yOne - 8}
          textAnchor="end"
          fill="currentColor"
          stroke="none"
          fontSize="12"
        >
          σ(x)
        </text>
        <text
          x={s.right}
          y={yZero + 17}
          textAnchor="end"
          fill="currentColor"
          stroke="none"
          opacity="0.8"
        >
          x
        </text>
      </g>
    </svg>
  )
}
