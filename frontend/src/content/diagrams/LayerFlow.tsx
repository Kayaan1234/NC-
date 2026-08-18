// Figures 13 and 14 — one layer's forward pass and one layer's backward pass.
//
// Both are shape diagrams rather than worked examples. The matrix page already
// showed what each operation does to actual numbers; what a reader needs here is
// which shape goes where, because every bug in a hand-written backward pass
// shows up first as a shape that does not line up.
//
// The sizes are the same throughout: batch 4, fan_in 3, fan_out 2. Reusing one
// set of numbers across the two figures means the second one can be read as a
// continuation of the first rather than as a fresh puzzle.
//
// Two exports from one file because they are the two halves of one story, and a
// change to the shapes has to land in both at once.

import { Arrow, Box, Brace } from './flow'
import { Frame, Note } from './matrix'

const WIDTH = 480

const BATCH = 4
const FAN_IN = 3
const FAN_OUT = 2
const shape = (r: number, c: number) => `${r} × ${c}`

// --- Figure 13: forward -------------------------------------------------------

/** Vertical band the row of boxes occupies, and the line the arrows run along. */
const F_BOX = { y: 76, h: 40 }
const F_MID = F_BOX.y + F_BOX.h / 2

export function LayerForward() {
  // Laid out left to right by accumulating widths, so nudging one box cannot
  // leave a gap or an overlap somewhere further along the row.
  const boxW = { input: 72, rest: 64 }
  const arrowW = [58, 56, 58]
  const x0 = 22

  const inputX = x0
  const a1 = inputX + boxW.input
  const zX = a1 + arrowW[0]
  const a2 = zX + boxW.rest
  const zbX = a2 + arrowW[1]
  const a3 = zbX + boxW.rest
  const aX = a3 + arrowW[2]

  /** Arrow along the row, drawn between two box edges. */
  const step = (from: number, w: number) => (
    <Arrow x1={from + 6} y1={F_MID} x2={from + w - 4} y2={F_MID} />
  )

  return (
    <Frame
      id="layer-forward-title"
      height={206}
      title="One layer's forward pass as a chain of shapes. A four by three input is multiplied by
        the three by two weight matrix to give a four by two z, the one by two bias row is added to
        it, and the activation function is applied to every cell, giving the four by two output a.
        A brace underneath marks z, z plus bias and a as three states of the single buffer named
        cache_output."
    >
      <Box x={inputX} y={F_BOX.y} w={boxW.input} h={F_BOX.h} lines={['input', shape(BATCH, FAN_IN)]} />
      <Box x={zX} y={F_BOX.y} w={boxW.rest} h={F_BOX.h} lines={['z', shape(BATCH, FAN_OUT)]} />
      <Box x={zbX} y={F_BOX.y} w={boxW.rest} h={F_BOX.h} lines={['z + bias', shape(BATCH, FAN_OUT)]} />
      <Box x={aX} y={F_BOX.y} w={boxW.rest} h={F_BOX.h} lines={['a', shape(BATCH, FAN_OUT)]} />

      {step(a1, arrowW[0])}
      {step(a2, arrowW[1])}
      {step(a3, arrowW[2])}

      {/* The two parameters drop in from above, onto the step that consumes
          them. Everything else on this row is a value passing through; these two
          are the things the layer owns and the things that learn. */}
      {[
        { cx: a1 + arrowW[0] / 2, name: `weight (${shape(FAN_IN, FAN_OUT)})`, op: 'matmul' },
        { cx: a2 + arrowW[1] / 2, name: `bias (${shape(1, FAN_OUT)})`, op: '+ bias' },
      ].map((p) => (
        <g key={p.op}>
          <Note x={p.cx} y={34}>
            {p.name}
          </Note>
          <Arrow x1={p.cx} y1={42} x2={p.cx} y2={F_MID - 8} opacity={0.5} />
          <Note x={p.cx} y={132}>
            {p.op}
          </Note>
        </g>
      ))}
      <Note x={a3 + arrowW[2] / 2} y={132}>
        apply f
      </Note>

      {/* z, z + bias and a are not three matrices. They are one. */}
      <Brace x={zX} y={146} w={aX + boxW.rest - zX} />
      <Note x={(zX + aX + boxW.rest) / 2} y={174}>
        cache_output
      </Note>
      <Note x={WIDTH / 2} y={196}>
        one buffer, written three times, kept until the batch size changes
      </Note>
    </Frame>
  )
}

// --- Figure 14: backward ------------------------------------------------------

const B_TARGETS = [
  {
    cx: 76,
    w: 112,
    lines: ['dL/db', shape(1, FAN_OUT)],
    notes: ['sum down the batch', 'into grad_bias'],
  },
  {
    cx: 240,
    w: 112,
    lines: ['dL/dW', shape(FAN_IN, FAN_OUT)],
    notes: ['transpose(input) · dL/dz', 'into grad_weight'],
  },
  {
    cx: 404,
    w: 124,
    lines: ['dL/dX', shape(BATCH, FAN_IN)],
    // Broken over two lines rather than one. On one line it runs to within a few
    // units of the middle branch's first note, and two labels that nearly touch
    // read as one label.
    notes: ['dL/dz ·', 'transpose(weight)'],
  },
]

const B_TOP = 172

export function LayerBackward() {
  return (
    <Frame
      id="layer-backward-title"
      height={294}
      title="One layer's backward pass. A four by two upstream gradient arrives, is multiplied
        elementwise by the activation's derivative to give dL/dz, and then splits three ways: a one
        by two bias gradient found by summing down the batch, a three by two weight gradient found
        by multiplying the transposed input by dL/dz, and a four by three input gradient found by
        multiplying dL/dz by the transposed weights, which is what the previous layer receives."
    >
      <Box x={192} y={16} w={96} h={40} lines={['dL/da', shape(BATCH, FAN_OUT)]} />
      <Arrow x1={240} y1={56} x2={240} y2={72} />

      <Box
        x={130}
        y={76}
        w={220}
        h={44}
        lines={["dL/dz = dL/da ⊙ f'(a)", shape(BATCH, FAN_OUT)]}
      />

      {B_TARGETS.map((t) => (
        <g key={t.lines[0]}>
          <Arrow x1={240} y1={120} x2={t.cx} y2={B_TOP - 4} />
          <Box x={t.cx - t.w / 2} y={B_TOP} w={t.w} h={40} lines={t.lines} />
          {t.notes.map((n, i) => (
            <Note key={n} x={t.cx} y={B_TOP + 60 + i * 14}>
              {n}
            </Note>
          ))}
        </g>
      ))}

      {/* Clear of the per-branch notes above, which run to y = 246. The two rows
          are 4 units apart at the obvious spacing, which reads as one paragraph. */}
      <Note x={WIDTH / 2} y={268}>
        every gradient comes out the shape of the thing it is the gradient of
      </Note>
      <Note x={WIDTH / 2} y={282}>
        two of them stay on the layer, the third is what the layer before receives
      </Note>
    </Frame>
  )
}
