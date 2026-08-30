// The drawing half of the step1 matrix figures: brackets, cells, operators and
// the figure shell. Every figure on matrix.hpp is "some grids, an operator, a
// result", so the geometry is written once in matrix-geometry.ts and the
// components here say what it means.
//
// This file exports components and nothing else, deliberately. A module that
// mixes components with plain helpers forces Fast Refresh to fall back to a full
// reload on every edit, which on a learn page means losing your scroll position
// in a long article to change one number in a figure. The arithmetic lives next
// door in matrix-geometry.ts; import from there when you need it.

import type { ReactNode } from 'react'
import {
  CELL,
  LABEL_DROP,
  PAD,
  SERIF,
  at,
  fmt,
  gridHeight,
  gridWidth,
  type M,
} from './matrix-geometry'

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
 * `format` overrides the default 2dp for a figure whose numbers do not survive
 * it: the softmax exponentials round to 1, 0.37, 0.14, 0.05, which visibly fail
 * to sum to the 1.55 printed beside them. A figure that shows a running total
 * has to print enough digits for the total to be checkable, so it asks for 3dp.
 */
export function Grid({
  a,
  x,
  y,
  cellW = CELL.w,
  cellH = CELL.h,
  emphasis,
  ghost = false,
  format = fmt,
}: {
  a: M
  x: number
  y: number
  cellW?: number
  cellH?: number
  emphasis?: (i: number, j: number) => boolean
  ghost?: boolean
  format?: (v: number) => string
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
            {format(at(a, i, j))}
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
      <g fontFamily="var(--font-fig)" fontSize="13" strokeWidth="1.25">
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
