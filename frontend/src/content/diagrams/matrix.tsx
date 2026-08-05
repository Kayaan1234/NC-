// Drawing matrices for the step1 figures — the same idea as plot.ts, one level up:
// plot.ts keeps a curve honest by sampling the real function, and this keeps a
// worked example honest by taking the numbers as data and laying the cells out
// from the shape. Every figure on matrix.hpp is "some grids, an operator, a
// result", so the geometry is written once here and the figures say what they
// mean.
//
// The rule that matters: a figure supplies its operands and DERIVES its result
// (`a.map((v, i) => v * b[i])`), never types the answer row out. A hand-typed
// product that is off by one is the error a reader has no defence against.
//
// A .tsx rather than a .ts because it exports components as well as geometry; it
// is lower-cased like plot.ts to say it is shared machinery, not a figure.

import type { ReactNode } from 'react'

/** A matrix as the figures pass it around: shape plus row-major values. */
export type M = {
  rows: number
  cols: number
  values: number[]
  /** Drawn under the brackets, e.g. "A (2×3)". */
  label?: string
}

export const CELL = { w: 36, h: 26 }
/** Gap between the brackets and the first/last column of cells. */
const PAD = 7
/** How far the bracket serifs stick out. */
const SERIF = 5
/** Distance from the bottom of the brackets down to the label's baseline. */
const LABEL_DROP = 16

export function m(rows: number, cols: number, values: number[], label?: string): M {
  if (values.length !== rows * cols) {
    // A figure with the wrong number of values would silently draw a ragged
    // grid; better to fail the render than to publish a wrong picture.
    throw new Error(`matrix ${label ?? ''}: ${rows}×${cols} needs ${rows * cols} values`)
  }
  return { rows, cols, values, label }
}

/** Row-major, exactly as Matrix::row_values is indexed: (i, j) → i * cols + j. */
export function at(a: M, i: number, j: number): number {
  return a.values[i * a.cols + j]
}

export function gridWidth(a: M, cellW = CELL.w): number {
  return a.cols * cellW + PAD * 2
}

export function gridHeight(a: M, cellH = CELL.h): number {
  return a.rows * cellH
}

/**
 * Short enough to sit inside a cell: integers plain, everything else to 2dp
 * with trailing zeros trimmed, so 0.5 does not read as 0.50 beside 0.73.
 */
export function fmt(v: number): string {
  if (Number.isInteger(v)) return String(v)
  const s = v.toFixed(2)
  return s.replace(/0+$/, '').replace(/\.$/, '')
}

/** Square brackets, drawn as line art rather than typeset as [ ] glyphs. */
function Brackets({ x, y, w, h }: { x: number; y: number; w: number; h: number }) {
  return (
    <g opacity="0.8">
      <path d={`M${x + SERIF} ${y}H${x}V${y + h}H${x + SERIF}`} />
      <path d={`M${x + w - SERIF} ${y}H${x + w}V${y + h}H${x + w - SERIF}`} />
    </g>
  )
}

/**
 * A bracketed matrix with its values in the cells.
 *
 * `emphasis` marks the cell(s) the surrounding prose is talking about — a ring
 * rather than a fill, since fills are reserved for var(--bg) knock-outs.
 * `ghost` dashes the brackets, used for the copies of a broadcast bias row that
 * do not really exist in memory.
 */
export function Grid({
  a,
  x,
  y,
  cellW = CELL.w,
  cellH = CELL.h,
  emphasis,
  ghost = false,
}: {
  a: M
  x: number
  y: number
  cellW?: number
  cellH?: number
  emphasis?: (i: number, j: number) => boolean
  ghost?: boolean
}) {
  const w = gridWidth(a, cellW)
  const h = gridHeight(a, cellH)
  const cells: ReactNode[] = []

  for (let i = 0; i < a.rows; i++) {
    for (let j = 0; j < a.cols; j++) {
      const cx = x + PAD + j * cellW + cellW / 2
      const cy = y + i * cellH + cellH / 2
      const on = emphasis?.(i, j) ?? false
      cells.push(
        <g key={`${i}-${j}`}>
          {on && (
            <rect
              x={cx - cellW / 2 + 2}
              y={cy - cellH / 2 + 2}
              width={cellW - 4}
              height={cellH - 4}
              rx="2"
              strokeWidth="1.25"
            />
          )}
          <text
            x={cx}
            y={cy + 4}
            textAnchor="middle"
            fill="currentColor"
            stroke="none"
            opacity={ghost ? 0.45 : on ? 1 : 0.9}
          >
            {fmt(at(a, i, j))}
          </text>
        </g>,
      )
    }
  }

  return (
    <g opacity={ghost ? 0.55 : 1} strokeDasharray={ghost ? '3 3' : undefined}>
      <Brackets x={x} y={y} w={w} h={h} />
      {cells}
      {a.label && (
        <text
          x={x + w / 2}
          y={y + h + LABEL_DROP}
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          fontSize="10"
          opacity="0.7"
          strokeDasharray="none"
        >
          {a.label}
        </text>
      )}
    </g>
  )
}

/** An operator or an "=" between two grids, on the shared vertical centre. */
export function Glyph({
  x,
  cy,
  children,
  size = 14,
}: {
  x: number
  cy: number
  children: ReactNode
  size?: number
}) {
  return (
    <text
      x={x}
      y={cy + size * 0.35}
      textAnchor="middle"
      fill="currentColor"
      stroke="none"
      fontSize={size}
      opacity="0.85"
    >
      {children}
    </text>
  )
}

/** The standard figure shell: sizing, the accessible title, mono type. */
export function Frame({
  id,
  title,
  width = 480,
  height,
  children,
}: {
  id: string
  title: string
  width?: number
  height: number
  children: ReactNode
}) {
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-labelledby={id}
      fill="none"
      stroke="currentColor"
      strokeOpacity="0.85"
      vectorEffect="non-scaling-stroke"
    >
      <title id={id}>{title}</title>
      <g fontFamily="var(--font-mono)" fontSize="12" strokeWidth="1.25">
        {children}
      </g>
    </svg>
  )
}

/** A caption line inside the figure, for the one thing to notice in it. */
export function Note({
  x,
  y,
  children,
  anchor = 'middle',
}: {
  x: number
  y: number
  children: ReactNode
  anchor?: 'start' | 'middle' | 'end'
}) {
  return (
    <text
      x={x}
      y={y}
      textAnchor={anchor}
      fill="currentColor"
      stroke="none"
      fontSize="10"
      opacity="0.7"
    >
      {children}
    </text>
  )
}
