// Figure 18 — one epoch, as the driver actually feeds it.
//
// The numbers are MNIST's defaults from Step1/main.cpp's apply_defaults(): a cap
// of 10000 training rows and a batch size of 64. The batch count is computed
// from those two rather than written down, because "157" is exactly the sort of
// number that survives a change to either one and quietly becomes wrong.
//
// Ten divisions are drawn where there are really 157. A figure cannot show 157
// slices of a 400 unit bar and stay legible, so it says so underneath instead of
// pretending.

import { Arrow, Box } from './flow'
import { Frame, Note } from './matrix'

const WIDTH = 480

const ROWS = 10000
const BATCH = 64
const BATCHES = Math.ceil(ROWS / BATCH)
const DRAWN = 10

const BAR = { x: 40, w: 400, h: 26 }
const BAR1_Y = 34
const BAR2_Y = 98

/**
 * The batch the figure follows down into the training step, and where the three
 * steps start.
 *
 * The row of steps hangs off the picked batch rather than being centred in the
 * canvas. Centring it puts the arrow's target 140 units sideways of its source,
 * which draws as a near-horizontal line that reads as a connection to whatever
 * it passes over rather than as a drop.
 */
const PICKED = 1
const SLICE = BAR.w / DRAWN
const PICKED_CX = BAR.x + (PICKED + 0.5) * SLICE

const STEPS = ['forward', 'backward', 'update']
const STEP_W = 94
const STEP_GAP = 32
const STEP_Y = 172
const STEP_X0 = PICKED_CX - STEP_W / 2

export default function MiniBatch() {
  return (
    <Frame
      id="minibatch-title"
      height={250}
      title="One epoch of mini-batch training. A bar represents the 10000 training rows in the
        order they were loaded. An arrow marked shuffle leads to a second bar of the same rows,
        now divided into batches of 64. One batch is picked out and leads down to three boxes in a
        row: forward, backward, update. The caption notes that 10000 rows in batches of 64 gives
        157 batches, and therefore 157 weight updates in a single epoch."
    >
      <Note x={WIDTH / 2} y={BAR1_Y - 8}>
        {`the training rows, in the order they were loaded (${ROWS})`}
      </Note>
      <rect x={BAR.x} y={BAR1_Y} width={BAR.w} height={BAR.h} rx="2" opacity="0.85" />

      <Arrow x1={WIDTH / 2} y1={BAR1_Y + BAR.h + 6} x2={WIDTH / 2} y2={BAR2_Y - 22} />
      <Note x={WIDTH / 2 + 10} y={BAR1_Y + BAR.h + 20} anchor="start">
        shuffled, every epoch
      </Note>

      <rect x={BAR.x} y={BAR2_Y} width={BAR.w} height={BAR.h} rx="2" opacity="0.85" />
      {/* Interior divisions only: the two ends are the bar's own outline. */}
      {Array.from({ length: DRAWN - 1 }, (_, i) => (
        <path
          key={i}
          d={`M${BAR.x + (i + 1) * SLICE} ${BAR2_Y}v${BAR.h}`}
          opacity="0.5"
          strokeDasharray="3 3"
        />
      ))}
      {/* The one the rest of the figure follows. */}
      <rect
        x={BAR.x + PICKED * SLICE}
        y={BAR2_Y}
        width={SLICE}
        height={BAR.h}
        strokeWidth="1.9"
      />
      <Note x={WIDTH / 2} y={BAR2_Y + BAR.h + 18}>
        {`cut into batches of ${BATCH} rows (drawn as ${DRAWN}, there are really ${BATCHES})`}
      </Note>

      <Arrow x1={PICKED_CX} y1={BAR2_Y + BAR.h + 26} x2={PICKED_CX} y2={STEP_Y - 5} />

      {STEPS.map((s, i) => {
        const x = STEP_X0 + i * (STEP_W + STEP_GAP)
        return (
          <g key={s}>
            <Box x={x} y={STEP_Y} w={STEP_W} h={34} lines={[s]} />
            {i < STEPS.length - 1 && (
              <Arrow
                x1={x + STEP_W + 5}
                y1={STEP_Y + 17}
                x2={x + STEP_W + STEP_GAP - 5}
                y2={STEP_Y + 17}
              />
            )}
          </g>
        )
      })}

      <Note x={WIDTH / 2} y={222}>
        {`${ROWS} rows in batches of ${BATCH} is ${BATCHES} batches, so ${BATCHES} weight updates in one epoch`}
      </Note>
      <Note x={WIDTH / 2} y={236}>
        {`hand all ${ROWS} over at once instead and the epoch buys you a single update`}
      </Note>
    </Frame>
  )
}
