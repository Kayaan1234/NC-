// Figures 4–8 — one worked example each for the elementwise half of matrix.hpp:
// the broadcast bias add, subtract, the Hadamard product, scale, and apply.
//
// Five named exports from one file rather than five files, for the reason
// Xor.tsx gives: they are one picture with the operator swapped, so they share
// their layout, their cell size and their vertical rhythm. Split up, the first
// one to move would leave the other four behind.
//
// Every result grid is COMPUTED from the operands below — `zip(A, B, (x, y) => x - y)`
// — never typed out. These figures exist to be trusted at a glance, and a
// hand-typed answer cell is exactly the error a reader cannot catch.

import { Frame, Glyph, Grid, Note } from './matrix'
import { gridHeight, gridWidth, m, type M } from './matrix-geometry'

// --- shared layout -----------------------------------------------------------

const WIDTH = 480
/** Vertical centre every operand is hung from. */
const CY = 46
const GAP = 10
const GLYPH_W = 24
const ARROW_W = 54

type Part =
  | { kind: 'grid'; a: M; ghost?: boolean; cellW?: number }
  | { kind: 'glyph'; text: string }
  /** An arrow with a label over it, for "put every element through f". */
  | { kind: 'arrow'; text: string }

const partWidth = (p: Part) =>
  p.kind === 'grid' ? gridWidth(p.a, p.cellW) : p.kind === 'arrow' ? ARROW_W : GLYPH_W

/** Lays the parts out left to right and centres the whole run in the canvas. */
function Row({ parts }: { parts: Part[] }) {
  const total = parts.reduce((w, p) => w + partWidth(p), 0) + GAP * (parts.length - 1)
  let x = (WIDTH - total) / 2

  return (
    <g>
      {parts.map((p, i) => {
        const w = partWidth(p)
        const left = x
        x += w + GAP

        if (p.kind === 'grid') {
          return (
            <Grid
              key={i}
              a={p.a}
              x={left}
              y={CY - gridHeight(p.a) / 2}
              ghost={p.ghost}
              cellW={p.cellW}
            />
          )
        }
        if (p.kind === 'glyph') {
          return (
            <Glyph key={i} x={left + w / 2} cy={CY}>
              {p.text}
            </Glyph>
          )
        }
        return (
          <g key={i}>
            <path d={`M${left + 4} ${CY}H${left + w - 8}`} opacity="0.8" />
            <path
              d={`M${left + w - 4} ${CY}l-6 -3.5v7z`}
              fill="currentColor"
              stroke="none"
              opacity="0.8"
            />
            <Note x={left + w / 2 - 2} y={CY - 9}>
              {p.text}
            </Note>
          </g>
        )
      })}
    </g>
  )
}

const HEIGHT = 124
const NOTE_Y = 110

/** Elementwise combine of two same-shape matrices — the shape the code enforces. */
function zip(a: M, b: M, f: (x: number, y: number) => number, label: string): M {
  return m(a.rows, a.cols, a.values.map((v, i) => f(v, b.values[i])), label)
}

function map(a: M, f: (x: number) => number, label: string): M {
  return m(a.rows, a.cols, a.values.map(f), label)
}

// --- Figure 4: the broadcast bias add ----------------------------------------

const ADD_A = m(2, 3, [1, 2, 3, 4, 5, 6], 'A (2×3)')
// Unlabelled: Grid hangs a label under its own brackets, which for a one-row
// Bias is exactly where the dashed copy sits. Labelled by hand below instead,
// on the same baseline as A's.
const BIAS = m(1, 3, [10, 20, 30])
// Bias.row_values[j] — the same three numbers reused for every row of A, which
// is what `A.row_values[i*columns + j] += Bias.row_values[j]` says.
const ADD_C = m(
  ADD_A.rows,
  ADD_A.cols,
  ADD_A.values.map((v, k) => v + BIAS.values[k % ADD_A.cols]),
  'A + Bias',
)

export function BiasBroadcast() {
  const aW = gridWidth(ADD_A)
  const bW = gridWidth(BIAS)
  const cW = gridWidth(ADD_C)
  const total = aW + bW + cW + GLYPH_W * 2 + GAP * 4
  const aX = (WIDTH - total) / 2
  const plusX = aX + aW + GAP
  const bX = plusX + GLYPH_W + GAP
  const eqX = bX + bW + GAP
  const cX = eqX + GLYPH_W + GAP

  return (
    <Frame
      id="matrix-bias-title"
      height={HEIGHT}
      title="A two by three matrix of 1 2 3 over 4 5 6, plus a one by three bias row of 10 20 30,
        equals 11 22 33 over 14 25 36. The bias row is drawn twice: solid once, then dashed
        underneath, because the same single row is added to every row of the matrix and the
        dashed copy is implied rather than stored."
    >
      <Grid a={ADD_A} x={aX} y={CY - gridHeight(ADD_A) / 2} />
      <Glyph x={plusX + GLYPH_W / 2} cy={CY}>
        +
      </Glyph>

      {/* The real row, and beneath it the copy the loop behaves as if it had.
          Dashed, because nothing in memory holds it. */}
      <Grid a={BIAS} x={bX} y={CY - gridHeight(ADD_A) / 2} />
      <Grid
        a={m(1, 3, BIAS.values)}
        x={bX}
        y={CY - gridHeight(ADD_A) / 2 + gridHeight(BIAS)}
        ghost
      />

      <Note x={bX + bW / 2} y={CY + gridHeight(ADD_A) / 2 + 16}>
        Bias (1×3)
      </Note>

      <Glyph x={eqX + GLYPH_W / 2} cy={CY}>
        =
      </Glyph>
      <Grid a={ADD_C} x={cX} y={CY - gridHeight(ADD_C) / 2} />

      <Note x={WIDTH / 2} y={NOTE_Y}>
        the dashed row is implied, never stored — Bias stays one row of three
      </Note>
    </Frame>
  )
}

// --- Figure 5: subtract ------------------------------------------------------

const SUB_A = m(2, 3, [5, 8, 2, 9, 4, 7], 'A (2×3)')
const SUB_B = m(2, 3, [1, 3, 2, 4, 4, 5], 'B (2×3)')
const SUB_C = zip(SUB_A, SUB_B, (x, y) => x - y, 'A − B')

export function Subtract() {
  return (
    <Frame
      id="matrix-subtract-title"
      height={HEIGHT}
      title="A two by three matrix of 5 8 2 over 9 4 7 minus a two by three matrix of 1 3 2 over
        4 4 5, giving 4 5 0 over 5 0 2. Each cell is paired with the cell in the same position,
        so both matrices must be the same shape."
    >
      <Row
        parts={[
          { kind: 'grid', a: SUB_A },
          { kind: 'glyph', text: '−' },
          { kind: 'grid', a: SUB_B },
          { kind: 'glyph', text: '=' },
          { kind: 'grid', a: SUB_C },
        ]}
      />
      <Note x={WIDTH / 2} y={NOTE_Y}>
        same position, same position — so the two shapes must match exactly
      </Note>
    </Frame>
  )
}

// --- Figure 6: the Hadamard product ------------------------------------------

const HAD_A = m(2, 3, [1, 2, 3, 4, 5, 6], 'A (2×3)')
const HAD_B = m(2, 3, [2, 0, 3, 1, 10, 2], 'B (2×3)')
const HAD_C = zip(HAD_A, HAD_B, (x, y) => x * y, 'A ⊙ B')

export function Hadamard() {
  return (
    <Frame
      id="matrix-hadamard-title"
      height={HEIGHT}
      title="A two by three matrix of 1 2 3 over 4 5 6, multiplied elementwise by 2 0 3 over
        1 10 2, giving 2 0 9 over 4 50 12. Nothing is summed: the cell in each position is simply
        multiplied by the cell in the same position."
    >
      <Row
        parts={[
          { kind: 'grid', a: HAD_A },
          { kind: 'glyph', text: '⊙' },
          { kind: 'grid', a: HAD_B },
          { kind: 'glyph', text: '=' },
          { kind: 'grid', a: HAD_C },
        ]}
      />
      <Note x={WIDTH / 2} y={NOTE_Y}>
        nothing is summed — this is not matmul, the shape comes out unchanged
      </Note>
    </Frame>
  )
}

// --- Figure 7: scale ---------------------------------------------------------

const SCALE_A = m(2, 3, [2, 4, 6, 8, 10, 12], 'A (2×3)')
const S = 0.5
const SCALE_C = map(SCALE_A, (v) => v * S, 'scale(A, 0.5)')

export function Scale() {
  return (
    <Frame
      id="matrix-scale-title"
      height={HEIGHT}
      title="A two by three matrix of 2 4 6 over 8 10 12, multiplied by the scalar 0.5, giving
        1 2 3 over 4 5 6. One number multiplies every cell."
    >
      <Row
        parts={[
          { kind: 'glyph', text: '0.5' },
          { kind: 'glyph', text: '×' },
          { kind: 'grid', a: SCALE_A },
          { kind: 'glyph', text: '=' },
          { kind: 'grid', a: SCALE_C },
        ]}
      />
      <Note x={WIDTH / 2} y={NOTE_Y}>
        one scalar over every cell — the 1/N in a gradient looks exactly like this
      </Note>
    </Frame>
  )
}

// --- Figure 8: apply, with sigmoid -------------------------------------------

const APPLY_A = m(2, 3, [0, 1, -1, 2, -2, 0.5], 'A (2×3)')
// The real σ, evaluated here rather than a table of remembered values — the same
// reason plot.ts samples a function instead of drawing its shape by eye.
const sigmoid = (x: number) => 1 / (1 + Math.exp(-x))
const APPLY_C = map(APPLY_A, sigmoid, 'apply(A, σ)')

export function ApplySigmoid() {
  return (
    <Frame
      id="matrix-apply-title"
      height={HEIGHT}
      title="A two by three matrix of 0, 1, minus 1 over 2, minus 2, 0.5 with the sigmoid applied
        to every cell, giving 0.5, 0.73, 0.27 over 0.88, 0.12, 0.62. Every value lands strictly
        between 0 and 1, and the shape is unchanged."
    >
      {/* Wider cells than the other figures: these are the only values with a
          decimal point, and at the default 36 the columns very nearly touch. */}
      <Row
        parts={[
          { kind: 'grid', a: APPLY_A, cellW: 46 },
          { kind: 'arrow', text: 'σ' },
          { kind: 'grid', a: APPLY_C, cellW: 46 },
        ]}
      />
      <Note x={WIDTH / 2} y={NOTE_Y}>
        σ runs over each cell in turn — same shape out, every value now in (0, 1)
      </Note>
    </Frame>
  )
}
