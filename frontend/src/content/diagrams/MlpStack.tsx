// Figure 15 — the whole MLP as a row of layers, with the forward lane above the
// arrows and the backward lane below them.
//
// The topology is the one the driver's own usage text suggests for MNIST,
// `--hidden 64,32`, so the reader can run the exact network in the picture. Every
// label is derived from SIZES: the layer boxes, the shapes carried between them
// and the shapes carried back. Typing the shapes out by hand is how a diagram
// ends up claiming a 64-wide layer hands on 32 numbers.
//
// The two lanes carry the SAME four shapes, which is the point of the figure. A
// gradient is the same size as the thing it is the gradient of, so nothing new
// has to be worked out to know what comes back.

import { Arrow, Box } from './flow'
import { Frame, Note } from './matrix'

/**
 * A shape label knocked out of whatever it sits on.
 *
 * The first and last labels straddle the dashed MLP::layers boundary, because
 * the stub they label is barely wider than they are and the boundary has to
 * cross it somewhere. Xor.tsx solves the same problem the same way: paint the
 * page background behind the glyphs first, so the line breaks rather than
 * running through the type.
 */
function Shape({ x, y, children }: { x: number; y: number; children: string }) {
  return (
    <text
      x={x}
      y={y}
      textAnchor="middle"
      fill="currentColor"
      fontSize="10"
      opacity="0.7"
      stroke="var(--bg)"
      strokeWidth="3"
      paintOrder="stroke"
    >
      {children}
    </text>
  )
}

const WIDTH = 480

/** layer_sizes as MLP.hpp takes it: 784 inputs, two hidden layers, 10 classes. */
const SIZES = [784, 64, 32, 10]
const ACTS = ['relu', 'relu', 'LINEAR']

const BOX = { w: 92, h: 64, y: 88 }
const GAP = 56
const ROW_W = SIZES.length - 1
const TOTAL = ROW_W * BOX.w + (ROW_W - 1) * GAP
const X0 = (WIDTH - TOTAL) / 2

const FORWARD_Y = 106
const BACKWARD_Y = 138
const STUB = 38

/** Left edge of layer i's box. */
const boxX = (i: number) => X0 + i * (BOX.w + GAP)

/**
 * The gaps an arrow can run through: the stub before the first box, one gap
 * between each pair of boxes, and the stub after the last. There are always
 * exactly as many as there are shapes travelling, which is what lets the labels
 * come straight off SIZES.
 */
const SEGMENTS = SIZES.map((_, i) => {
  const left = i === 0 ? boxX(0) - STUB : boxX(i - 1) + BOX.w
  const right = i === ROW_W ? boxX(ROW_W - 1) + BOX.w + STUB : boxX(i)
  return { left, right, mid: (left + right) / 2 }
})

export default function MlpStack() {
  return (
    <Frame
      id="mlp-stack-title"
      height={244}
      title="Three layers in a row: 784 to 64 with relu, 64 to 32 with relu, and 32 to 10 with a
        linear activation. Arrows above run left to right carrying activations of shape N by 784,
        N by 64, N by 32 and N by 10; arrows below run right to left carrying gradients of exactly
        the same four shapes. A dashed outline groups the three layers, with softmax and
        cross-entropy left outside it."
    >
      {/* The dashed boundary is the reason the last layer is LINEAR: everything
          inside it is MLP::layers, and the loss lives outside. */}
      <Box
        x={X0 - 14}
        y={BOX.y - 12}
        w={TOTAL + 28}
        h={BOX.h + 28}
        lines={[]}
        dashed
      />
      <Note x={X0 - 14} y={BOX.y - 20} anchor="start">
        MLP::layers
      </Note>

      {ACTS.map((act, i) => (
        <Box
          key={act + i}
          x={boxX(i)}
          y={BOX.y}
          w={BOX.w}
          h={BOX.h}
          lines={[`Layer ${i}`, `${SIZES[i]} → ${SIZES[i + 1]}`, act]}
        />
      ))}

      {SEGMENTS.map((s, i) => (
        <g key={s.mid}>
          <Arrow x1={s.left + 5} y1={FORWARD_Y} x2={s.right - 5} y2={FORWARD_Y} />
          <Shape x={s.mid} y={FORWARD_Y - 8}>{`N×${SIZES[i]}`}</Shape>
          <Arrow x1={s.right - 5} y1={BACKWARD_Y} x2={s.left + 5} y2={BACKWARD_Y} />
          <Shape x={s.mid} y={BACKWARD_Y + 14}>{`N×${SIZES[i]}`}</Shape>
        </g>
      ))}

      <Note x={WIDTH / 2} y={192}>
        forward, on top: every layer hands its output straight to the next one
      </Note>
      <Note x={WIDTH / 2} y={206}>
        backward, underneath: the same four shapes come back, in reverse order
      </Note>
      <Note x={WIDTH / 2} y={228}>
        softmax and cross-entropy sit outside the dashed box, so Layer 2 stays LINEAR
      </Note>
    </Frame>
  )
}
