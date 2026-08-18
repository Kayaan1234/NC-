// Figures 11–12 — the two worked examples on math.hpp: one row through softmax,
// and a batch of two through cross-entropy.
//
// The rule from matrix.tsx applies with force here, because these are the
// figures a reader will check their own arithmetic against: every stage supplies
// only the stage before it and DERIVES the rest. The exponentials are
// Math.exp of the shifted logits, the sum is a reduce over those exponentials,
// the probabilities are that sum divided back through, and the losses are
// -Math.log of the cells the one-hot truth selects. Nothing on either figure is
// a number I typed out and hoped was right.
//
// Both print 3dp, via Grid's `format`: at the default 2dp the exponentials read
// 1, 0.37, 0.14, 0.05, which sum to 1.56 while the figure prints their total as
// 1.55. A stage that shows a running total has to print enough digits for the
// total to be checkable.

import { Frame, Grid, Note, gridHeight, gridWidth, m, type M } from './matrix'

const WIDTH = 480
const D3 = (v: number) => v.toFixed(3)

/** A downward arrow between two stacked stages, labelled to its right. */
function Step({ x, from, to, label }: { x: number; from: number; to: number; label: string }) {
  return (
    <g>
      <path d={`M${x} ${from}V${to - 5}`} opacity="0.8" />
      <path d={`M${x} ${to} l-3.5 -5h7z`} fill="currentColor" stroke="none" opacity="0.8" />
      <Note x={x + 9} y={(from + to) / 2 + 4} anchor="start">
        {label}
      </Note>
    </g>
  )
}

// --- Figure 11: softmax over one row of four logits --------------------------

// One sample's raw scores, the only typed numbers on the figure.
const LOGITS = [2, 1, 0, -1]

const ROW_MAX = Math.max(...LOGITS)
const SHIFTED = LOGITS.map((z) => z - ROW_MAX)
const EXPS = SHIFTED.map(Math.exp)
const SUM = EXPS.reduce((t, e) => t + e, 0)
const PROBS = EXPS.map((e) => e / SUM)

const SM_CELL = 58
const SM_X = 104
const SM_ROWS = [26, 84, 142, 200]
const SM_H = 26

/** Stage label to the left of a row, on that row's vertical centre. */
function Stage({ y, children }: { y: number; children: string }) {
  return (
    <Note x={SM_X - 12} y={y + SM_H / 2 + 4} anchor="end">
      {children}
    </Note>
  )
}

export function SoftmaxWorked() {
  const gw = gridWidth(m(1, 4, LOGITS), SM_CELL)
  const mid = SM_X + gw / 2
  const rightOf = SM_X + gw + 14

  const row = (values: number[]) => m(1, 4, values)
  const stage = (i: number, values: number[], format?: (v: number) => string) => (
    <Grid a={row(values)} x={SM_X} y={SM_ROWS[i]} cellW={SM_CELL} format={format} />
  )

  return (
    <Frame
      id="softmax-worked-title"
      width={WIDTH}
      height={262}
      title={`Softmax worked through on one row of four logits, ${LOGITS.join(', ')}. Subtracting
        the row maximum of ${ROW_MAX} gives ${SHIFTED.join(', ')}. Exponentiating gives
        ${EXPS.map(D3).join(', ')}, which total ${D3(SUM)}. Dividing each by that total gives the
        probabilities ${PROBS.map(D3).join(', ')}, which sum to one.`}
    >
      <Stage y={SM_ROWS[0]}>z (logits)</Stage>
      {stage(0, LOGITS)}

      <Step x={mid} from={SM_ROWS[0] + SM_H + 4} to={SM_ROWS[1] - 4} label={`− max = ${ROW_MAX}`} />

      <Stage y={SM_ROWS[1]}>z − max</Stage>
      {stage(1, SHIFTED)}

      <Step x={mid} from={SM_ROWS[1] + SM_H + 4} to={SM_ROWS[2] - 4} label="exp" />

      <Stage y={SM_ROWS[2]}>exp(z − max)</Stage>
      {stage(2, EXPS, D3)}
      <Note x={rightOf} y={SM_ROWS[2] + SM_H / 2 + 4} anchor="start">
        {`Σ = ${D3(SUM)}`}
      </Note>

      <Step x={mid} from={SM_ROWS[2] + SM_H + 4} to={SM_ROWS[3] - 4} label={`÷ ${D3(SUM)}`} />

      <Stage y={SM_ROWS[3]}>softmax(z)</Stage>
      {stage(3, PROBS, D3)}
      <Note x={rightOf} y={SM_ROWS[3] + SM_H / 2 + 4} anchor="start">
        {`Σ = ${D3(PROBS.reduce((t, p) => t + p, 0))}`}
      </Note>

      <Note x={WIDTH / 2} y={248}>
        the shift changes every exponent, and changes none of the answers
      </Note>
    </Frame>
  )
}

// --- Figure 12: cross-entropy over a batch of two ----------------------------

// Two samples, three classes. Only these eight numbers are typed; the losses and
// the batch mean below are computed from them.
const PRED = m(2, 3, [0.7, 0.2, 0.1, 0.1, 0.3, 0.6], 'pred (2×3)')
const TRUTH = m(2, 3, [1, 0, 0, 0, 0, 1], 'truth (one-hot)')

/** −Σⱼ yᵢⱼ log pᵢⱼ, one entry per row — exactly the inner loop of the code. */
function rowLosses(pred: M, truth: M): number[] {
  const out: number[] = []
  for (let i = 0; i < pred.rows; i++) {
    let acc = 0
    for (let j = 0; j < pred.cols; j++) {
      const k = i * pred.cols + j
      acc += truth.values[k] * Math.log(pred.values[k])
    }
    out.push(-acc)
  }
  return out
}

const ROW_LOSSES = rowLosses(PRED, TRUTH)
const MEAN_LOSS = ROW_LOSSES.reduce((t, l) => t + l, 0) / PRED.rows
const CE_CY = 50
const hot = (i: number, j: number) => TRUTH.values[i * TRUTH.cols + j] === 1

export function CrossEntropyWorked() {
  // Sized to fit the four parts and their three gaps inside WIDTH, then centred:
  // 2×128 for the grids, 72 for the arrow, 70 for the loss column. The gap is
  // wide enough that pred's closing bracket and truth's opening one do not read
  // as one long bracket.
  const cellW = 38
  const gap = 18
  const predW = gridWidth(PRED, cellW)
  const arrowW = 72
  const lossCellW = 56
  const lossW = gridWidth(m(2, 1, ROW_LOSSES), lossCellW)
  const total = predW * 2 + arrowW + lossW + gap * 3
  const predX = (WIDTH - total) / 2
  const truthX = predX + predW + gap
  const arrowX = truthX + predW + gap
  const lossX = arrowX + arrowW + gap
  const top = CE_CY - gridHeight(PRED) / 2

  return (
    <Frame
      id="cross-entropy-worked-title"
      width={WIDTH}
      height={152}
      title={`Cross-entropy on a batch of two samples over three classes. The predicted
        distributions are 0.7, 0.2, 0.1 and 0.1, 0.3, 0.6; the one-hot truths select the first
        class for the first sample and the third for the second. Only the selected probabilities
        contribute, giving per-sample losses of ${ROW_LOSSES.map(D3).join(' and ')}, whose mean
        over the batch is ${D3(MEAN_LOSS)}.`}
    >
      <Grid a={PRED} x={predX} y={top} cellW={cellW} emphasis={hot} />
      <Grid a={TRUTH} x={truthX} y={top} cellW={cellW} emphasis={hot} />

      <g>
        <path d={`M${arrowX} ${CE_CY}H${arrowX + arrowW - 6}`} opacity="0.8" />
        <path
          d={`M${arrowX + arrowW} ${CE_CY}l-6 -3.5v7z`}
          fill="currentColor"
          stroke="none"
          opacity="0.8"
        />
        <Note x={arrowX + arrowW / 2} y={CE_CY - 9}>
          −Σⱼ y log p
        </Note>
        <Note x={arrowX + arrowW / 2} y={CE_CY + 18}>
          per row
        </Note>
      </g>

      <Grid
        a={m(2, 1, ROW_LOSSES, 'per-sample loss')}
        x={lossX}
        y={top}
        cellW={lossCellW}
        format={D3}
      />

      <Note x={WIDTH / 2} y={128}>
        {`mean over the batch: (${ROW_LOSSES.map(D3).join(' + ')}) ÷ ${PRED.rows} = ${D3(MEAN_LOSS)}`}
      </Note>
      <Note x={WIDTH / 2} y={142}>
        only the ringed cells contribute — every other term is 0 × log p
      </Note>
    </Frame>
  )
}
