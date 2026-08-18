// Shared line art for the step1 figures that are a pipeline rather than a
// matrix: labelled boxes joined by arrows. layer.hpp and MLP.hpp are both "a
// value goes in, a few things happen to it, a value comes out", so the same two
// primitives draw every figure on both pages.
//
// Arrowheads are explicit paths rather than an SVG <marker>. A marker needs an
// id, and several of these figures sit on one page, so one shared marker id
// would appear two or three times in the same document. Identical markers do
// happen to render correctly through that, but the duplicate id is invalid all
// the same, and drawing the triangle costs four numbers.
//
// Frame, Note and Glyph are imported from ./matrix by the figures that use this
// file. They are the figure shell, the small caption line and the centred
// operator glyph, and none of the three is specific to matrices.
//
// Components only, no plain helpers, for the reason matrix.tsx gives: a module
// that mixes the two drops Fast Refresh back to a full page reload, which on a
// long article means losing your scroll position to change one number.

/** Arrowhead half-width and length, in user units. */
const HEAD = { w: 3.5, len: 6 }
/** Baseline-to-baseline spacing of the text lines inside a Box. */
const LINE = 15

/** A straight arrow in any direction, with the head trimmed off the shaft. */
export function Arrow({
  x1,
  y1,
  x2,
  y2,
  opacity = 0.8,
}: {
  x1: number
  y1: number
  x2: number
  y2: number
  opacity?: number
}) {
  const len = Math.hypot(x2 - x1, y2 - y1) || 1
  const ux = (x2 - x1) / len
  const uy = (y2 - y1) / len
  // Base of the head, and the perpendicular that gives it its two back corners.
  const bx = x2 - ux * HEAD.len
  const by = y2 - uy * HEAD.len
  const px = -uy * HEAD.w
  const py = ux * HEAD.w

  return (
    <g opacity={opacity}>
      <path d={`M${x1} ${y1}L${bx} ${by}`} />
      <path
        d={`M${x2} ${y2}L${bx + px} ${by + py}L${bx - px} ${by - py}z`}
        fill="currentColor"
        stroke="none"
      />
    </g>
  )
}

/**
 * A rounded box holding one to three centred lines of text.
 *
 * The first line is the name and the rest are dimmed, which is what makes a
 * column of boxes scan as names first and detail second. The whole block is
 * centred vertically in the box, so boxes of different line counts still line
 * up on the same middle.
 *
 * `dashed` is for a boundary rather than a value: the outline round MLP::layers
 * in Figure 15, which groups the real boxes without being one.
 */
export function Box({
  x,
  y,
  w,
  h,
  lines,
  dashed = false,
}: {
  x: number
  y: number
  w: number
  h: number
  lines: string[]
  dashed?: boolean
}) {
  const top = y + (h - lines.length * LINE) / 2 + 11

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx="3"
        opacity={dashed ? 0.5 : 0.85}
        strokeDasharray={dashed ? '4 3' : undefined}
      />
      {lines.map((text, i) => (
        <text
          key={text}
          x={x + w / 2}
          y={top + i * LINE}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          fontSize={i === 0 ? 11 : 10}
          opacity={i === 0 ? 1 : 0.75}
        >
          {text}
        </text>
      ))}
    </g>
  )
}

/**
 * A horizontal curly brace under a run of boxes, for naming the thing they
 * share. Drawn as two quarter-turns meeting at a centre tick rather than as a
 * "{" glyph, so it stretches to any width without the type distorting.
 */
export function Brace({ x, y, w }: { x: number; y: number; w: number }) {
  const mid = x + w / 2
  const r = 6
  return (
    <path
      d={
        `M${x} ${y}q0 ${r} ${r} ${r}H${mid - r}q${r} 0 ${r} ${r}` +
        `q0 ${-r} ${r} ${-r}H${x + w - r}q${r} 0 ${r} ${-r}`
      }
      opacity="0.6"
    />
  )
}
