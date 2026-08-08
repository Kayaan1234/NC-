// Figure 3 — the one the matmul section leans on, in three stacked panels, as
// the author's cue asked: how an (i, j) becomes one offset, what the shape rule
// is, and then the first three passes of the loop with that arithmetic worked
// out on real numbers.
//
// Stacked rather than split into three figures because it is one cue and one
// argument: the third panel is unreadable without the first. Tall and 480 wide,
// since .figure svg caps at 100% of the prose column — going wider would only
// shrink the type.
//
// The trace in panel (c) is SIMULATED, not transcribed: `out` below is a real
// array that the same i/j/k loop from matrix.hpp accumulates into, so the
// running values are whatever the code would actually produce.

import { Frame, Grid, Note } from './matrix'
import { gridHeight, gridWidth, m } from './matrix-geometry'

const WIDTH = 480

// The operands, in the shapes the prose needs: A's columns match B's rows.
const A = m(2, 3, [1, 2, 3, 4, 5, 6])
const B = m(3, 2, [7, 8, 9, 10, 11, 12])
const N = A.cols // shared dimension
const P = B.cols

/** matmul() from matrix.hpp, verbatim in its loop order, so C is really A·B. */
function matmul(a: typeof A, b: typeof B) {
  const out = new Array(a.rows * b.cols).fill(0)
  for (let i = 0; i < a.rows; i++)
    for (let j = 0; j < a.cols; j++) {
      const av = a.values[i * a.cols + j]
      for (let k = 0; k < b.cols; k++) out[i * b.cols + k] += av * b.values[j * b.cols + k]
    }
  return m(a.rows, b.cols, out)
}

const C = matmul(A, B)

// --- panel (a): one index, not two -------------------------------------------

const FLAT = m(1, 6, A.values)
const PICK = { i: 1, j: 2 }
const OFFSET = PICK.i * A.cols + PICK.j

const A_X = 40
const A_Y = 34
const A_CY = A_Y + gridHeight(A) / 2
const FLAT_X = 214

// --- panel (b): the shape rule -----------------------------------------------

const B_CY = 200
const ROW_W = gridWidth(A) + gridWidth(B) + gridWidth(C) + 24 * 2 + 10 * 4
const BX_A = (WIDTH - ROW_W) / 2
const BX_MUL = BX_A + gridWidth(A) + 10
const BX_B = BX_MUL + 24 + 10
const BX_EQ = BX_B + gridWidth(B) + 10
const BX_C = BX_EQ + 24 + 10
const LABEL_Y = 258

// --- panel (c): the first three passes ---------------------------------------

/** Replays the loop, capturing what each of the first three passes did. */
function trace(steps: number) {
  const out = new Array(A.rows * P).fill(0)
  const rows: { ijk: string; a: string; inner: string; running: string }[] = []
  let done = 0
  for (let i = 0; i < A.rows && done < steps; i++)
    for (let j = 0; j < N && done < steps; j++) {
      const av = A.values[i * N + j]
      for (let k = 0; k < P && done < steps; k++) {
        const bv = B.values[j * P + k]
        out[i * P + k] += av * bv
        rows.push({
          ijk: `(i,j,k)=(${i},${j},${k})`,
          a: `a = A[${i}*${N}+${j}] = ${av}`,
          inner: `out[${i}*${P}+${k}] += a * B[${j}*${P}+${k}]`,
          running: `out[${i * P + k}] = ${out[i * P + k]}`,
        })
        done++
      }
    }
  return rows
}

const STEPS = trace(3)
const PANEL_C_Y = 300
const STEP_Y = 324
const STEP_DY = 22
const COL = { ijk: 18, a: 116, inner: 222, running: 388 }

export default function MatrixIndex() {
  return (
    <Frame
      id="matrix-index-title"
      height={418}
      width={WIDTH}
      title="Three panels. First: a two by three matrix of 1 2 3 over 4 5 6 beside the same six
        values in one flat row, with the cell at row 1 column 2 ringed in both, showing that
        (i, j) becomes the single offset i times columns plus j, here 1 times 3 plus 2 equals 5.
        Second: A, two by three, times B, three by two, gives a two by two result of 58 64 over
        139 154 — A's column count must equal B's row count. Third: the first three passes of the
        loop written out, showing a hoisted out of the innermost loop and the output cell being
        accumulated into rather than assigned."
    >
      {/* (a) --------------------------------------------------------------- */}
      <Note x={18} y={20} anchor="start">
        (a) an (i, j) is one offset into the flat row
      </Note>

      <Grid a={A} x={A_X} y={A_Y} emphasis={(i, j) => i === PICK.i && j === PICK.j} />
      <path d={`M${A_X + gridWidth(A) + 14} ${A_CY}H${FLAT_X - 20}`} opacity="0.7" />
      <path
        d={`M${FLAT_X - 14} ${A_CY}l-6 -3.5v7z`}
        fill="currentColor"
        stroke="none"
        opacity="0.7"
      />
      <Grid
        a={FLAT}
        x={FLAT_X}
        y={A_CY - gridHeight(FLAT) / 2}
        emphasis={(_, j) => j === OFFSET}
      />

      <Note x={WIDTH / 2} y={116}>
        (i, j) → i * columns + j &nbsp;&nbsp; ({PICK.i}, {PICK.j}) → {PICK.i} * {A.cols} +{' '}
        {PICK.j} = {OFFSET}
      </Note>

      {/* (b) --------------------------------------------------------------- */}
      <Note x={18} y={152} anchor="start">
        (b) the shape rule, and the result it fixes
      </Note>

      <Grid a={A} x={BX_A} y={B_CY - gridHeight(A) / 2} />
      <Note x={BX_MUL + 12} y={B_CY + 4}>
        ×
      </Note>
      <Grid a={B} x={BX_B} y={B_CY - gridHeight(B) / 2} />
      <Note x={BX_EQ + 12} y={B_CY + 4}>
        =
      </Note>
      <Grid a={C} x={BX_C} y={B_CY - gridHeight(C) / 2} />

      {/* Labels on one baseline rather than hung off each grid, which would step
          down with B's extra row. */}
      <Note x={BX_A + gridWidth(A) / 2} y={LABEL_Y}>
        A ({A.rows}×{A.cols})
      </Note>
      <Note x={BX_B + gridWidth(B) / 2} y={LABEL_Y}>
        B ({B.rows}×{B.cols})
      </Note>
      <Note x={BX_C + gridWidth(C) / 2} y={LABEL_Y}>
        C ({C.rows}×{C.cols})
      </Note>
      <Note x={WIDTH / 2} y={LABEL_Y + 16}>
        A.columns must equal B.rows — the {N} in the middle cancels, the outsides survive
      </Note>

      {/* (c) --------------------------------------------------------------- */}
      <Note x={18} y={PANEL_C_Y} anchor="start">
        (c) the first three passes, with the offsets worked out
      </Note>

      <g fontSize="10">
        {STEPS.map((s, r) => {
          const y = STEP_Y + r * STEP_DY
          return (
            <g key={r} opacity={0.9}>
              <text x={COL.ijk} y={y} fill="currentColor" stroke="none" opacity="0.75">
                {s.ijk}
              </text>
              <text x={COL.a} y={y} fill="currentColor" stroke="none">
                {s.a}
              </text>
              <text x={COL.inner} y={y} fill="currentColor" stroke="none">
                {s.inner}
              </text>
              <text x={COL.running} y={y} fill="currentColor" stroke="none" opacity="0.75">
                {s.running}
              </text>
            </g>
          )
        })}
      </g>

      {/* Two lines: one run of this at font 10 overflows 480 and is clipped by
          the viewBox — silently, since SVG text does not wrap. */}
      <Note x={18} y={392} anchor="start">
        a is read once per j and reused across every k.
      </Note>
      <Note x={18} y={406} anchor="start">
        out[…] is added to, never assigned — which is why it starts zeroed.
      </Note>
    </Frame>
  )
}
