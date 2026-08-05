// Figure 2 — the same nine numbers twice: as the 3×3 grid you picture, and as the
// single contiguous run of doubles that Matrix::row_values actually is.
//
// The values are 0..8 on purpose (the author's spec): the reader can read the
// mapping straight off the numbers, so the figure needs no index arithmetic to
// explain itself. That arithmetic is Figure 3's job, and putting it here would
// answer a question the page has not asked yet.

import { Frame, Grid, Note, CELL, gridWidth, m } from './matrix'

const A = m(3, 3, [0, 1, 2, 3, 4, 5, 6, 7, 8], 'the matrix you picture')
// The flat form is the same values in the same row-major order — derived, not
// re-typed, so the two halves of the figure cannot disagree. No label of its
// own: the row brackets hang directly under it, and Grid's label would land on
// top of them.
const FLAT = m(1, 9, A.values)

const A_W = gridWidth(A)
const A_X = (480 - A_W) / 2
const A_Y = 20

const F_W = gridWidth(FLAT)
const F_X = (480 - F_W) / 2
const F_Y = 158
/** Top of the row brackets, clear of the flat row's cells. */
const BRACE_Y = F_Y + CELL.h + 8

/** Where cell `k` of the flat row starts and ends, in user units. */
const cellLeft = (k: number) => F_X + 7 + k * CELL.w

export default function MatrixFlat() {
  return (
    <Frame
      id="matrix-flat-title"
      height={250}
      title="The numbers 0 to 8 shown twice. Above, as a 3 by 3 matrix with rows 0 1 2, then 3 4 5,
        then 6 7 8. Below, as a single row of nine values 0 through 8, the order they occupy in
        memory. Brackets under the flat row group it into three stretches of three, one per row of
        the matrix, showing that the rows are stored one after another."
    >
      <Grid a={A} x={A_X} y={A_Y} />
      <Grid a={FLAT} x={F_X} y={F_Y} />

      {/* One bracket per row of the matrix, under its stretch of the flat row. */}
      {[0, 1, 2].map((r) => {
        const x0 = cellLeft(r * 3)
        const x1 = cellLeft(r * 3 + 3)
        return (
          <g key={r} opacity="0.6">
            <path d={`M${x0} ${BRACE_Y}V${BRACE_Y + 6}H${x1}V${BRACE_Y}`} />
            <Note x={(x0 + x1) / 2} y={BRACE_Y + 20}>
              row {r}
            </Note>
          </g>
        )
      })}

      <Note x={240} y={140}>
        stored row after row, end to end
      </Note>
      <Note x={240} y={BRACE_Y + 42}>
        row_values — one contiguous block
      </Note>
    </Frame>
  )
}
