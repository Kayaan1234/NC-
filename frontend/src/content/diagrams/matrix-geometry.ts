// The geometry half of the step1 matrix figures — shape, indexing and layout
// arithmetic, with no JSX. Same idea as plot.ts one level up: plot.ts keeps a
// curve honest by sampling the real function, and this keeps a worked example
// honest by taking the numbers as data and laying the cells out from the shape.
//
// The rule that matters: a figure supplies its operands and DERIVES its result
// (`a.map((v, i) => v * b[i])`), never types the answer row out. A hand-typed
// product that is off by one is the error a reader has no defence against.
//
// Split out of matrix.tsx so that file exports components and nothing else,
// which is what lets Fast Refresh reload a figure without dropping the page's
// state. Lower-cased like plot.ts to say it is shared machinery, not a figure.

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
export const PAD = 7
/** How far the bracket serifs stick out. */
export const SERIF = 5
/** Distance from the bottom of the brackets down to the label's baseline. */
export const LABEL_DROP = 16

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
