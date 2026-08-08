// demo.ts — the landing page's in-browser training run.
//
// What these tests can and cannot catch, stated plainly so nobody reads more
// into a green run than is there:
//
//   CAN catch — a regression in the TypeScript. The arithmetic is deterministic
//   (seeded PRNG, fixed epochs), so any change to the forward pass, the gradient,
//   the loss clamp or the line formatting shows up here.
//
//   CANNOT catch — drift between this port and the C++ it mirrors
//   (services/Step0/logistic_regression.hpp). The expectations below are
//   generated from this file, so both sides moving apart is invisible to them.
//   Catching that needs a g++-gated comparison against the real binary, which
//   this suite deliberately does not do.
//
// Two things are pointedly NOT asserted:
//   * numeric parity with a server-side run — std::mt19937 is not reproduced, so
//     the initial weights and therefore the loss values differ by design;
//   * XOR accuracy — the weights collapse to ~0, so every prediction sits exactly
//     on the 0.5 threshold and the figure is decided by float residue of order
//     1e-9. `solved` is the stable question.

import { describe, expect, it } from 'vitest'

import { run } from './demo'
import type { DatasetName } from './demo'

describe('the outcome', () => {
  it('fits the linearly separable dataset', () => {
    // A single neuron draws one straight line, and `tiny` is separable by one.
    expect(run('tiny').solved).toBe(true)
  })

  it('fails to fit XOR, which is the entire point of the demo', () => {
    // Not a bug being pinned — this is the pedagogical payload. If it ever
    // passes, either the maths broke or the dataset stopped being XOR, and
    // either way the landing page is now telling the visitor something false.
    expect(run('xor').solved).toBe(false)
  })

  it('reaches full accuracy on tiny and short of it on xor', () => {
    const finalLine = (d: DatasetName) =>
      run(d).lines.find((l) => l.kind === 'final')!.text

    expect(finalLine('tiny')).toBe('final accuracy 100.0000%')
    expect(finalLine('xor')).not.toBe('final accuracy 100.0000%')
  })
})

describe('determinism', () => {
  it.each<DatasetName>(['tiny', 'xor'])(
    'produces an identical run every time for %s',
    (dataset) => {
      // Seeded on purpose: "Run again" has to reproduce the run, or the demo
      // looks like a random-number generator rather than training.
      expect(run(dataset)).toEqual(run(dataset))
    },
  )

  it('gives the two datasets different runs', () => {
    expect(run('tiny').lines).not.toEqual(run('xor').lines)
  })
})

describe('the log', () => {
  it('opens with a header naming the hyperparameters the real CLI would print', () => {
    const [header] = run('tiny').lines
    expect(header.kind).toBe('header')
    expect(header.text).toBe(
      '=== training: dataset=tiny lr=0.5 epochs=500 samples=3 features=2 seed=42 ===',
    )
  })

  it('ends with a final line then a RESULT line', () => {
    const kinds = run('tiny').lines.map((l) => l.kind)
    expect(kinds.slice(-2)).toEqual(['final', 'result'])
  })

  it('prints ten progress lines plus the last epoch', () => {
    // 500 epochs printing every 50 gives ten, and epoch 499 is forced. The
    // terminal block on the landing page is sized for exactly this height.
    const epochs = run('tiny').lines.filter((l) => l.kind === 'epoch')
    expect(epochs).toHaveLength(11)
  })

  it('formats an epoch line to the column widths main.cpp uses', () => {
    const [first] = run('tiny').lines.filter((l) => l.kind === 'epoch')
    // `epoch %4d  loss %.4f  acc %.4f%%` — the padding is load-bearing, since
    // this is meant to read as terminal output.
    expect(first.text).toMatch(/^epoch {4}0 {2}loss \d+\.\d{4} {2}acc \d+\.\d{4}%$/)
  })

  it('numbers the epoch lines 0, 50, 100 ... 450, then 499', () => {
    const numbers = run('tiny')
      .lines.filter((l) => l.kind === 'epoch')
      .map((l) => Number(l.text.slice('epoch'.length, 'epoch'.length + 5).trim()))

    expect(numbers).toEqual([0, 50, 100, 150, 200, 250, 300, 350, 400, 450, 499])
  })

  it('emits a RESULT line matching the binary machine-readable contract', () => {
    const result = run('tiny').lines.at(-1)!
    expect(result.kind).toBe('result')
    // The backend's runner parses exactly this shape: `RESULT ` then one JSON
    // object, last line wins (services/runner.py::_parse_result_line).
    expect(result.text.startsWith('RESULT ')).toBe(true)

    const parsed = JSON.parse(result.text.slice('RESULT '.length))
    expect(parsed).toMatchObject({
      dataset: 'tiny',
      learning_rate: 0.5,
      epochs: 500,
      samples: 3,
      features: 2,
      seed: 42,
      diverged: false,
    })
    expect(typeof parsed.final_loss).toBe('number')
    expect(parsed.final_accuracy).toBe(1)
  })

  it('reports xor in its own RESULT line without claiming success', () => {
    const parsed = JSON.parse(run('xor').lines.at(-1)!.text.slice('RESULT '.length))
    expect(parsed.dataset).toBe('xor')
    expect(parsed.samples).toBe(4)
    expect(parsed.final_accuracy).toBeLessThan(1)
  })
})

describe('the model snapshots', () => {
  it('carries the weights as of each line, so the readout can advance in step', () => {
    const { lines } = run('tiny')
    for (const line of lines) {
      expect(line.w).toHaveLength(2)
      expect(line.w.every(Number.isFinite)).toBe(true)
      expect(Number.isFinite(line.b)).toBe(true)
    }
  })

  it('snapshots are independent copies, not aliases of the live weight vector', () => {
    // `[...w]` at each snapshot. Without the copy every line would show the
    // final weights and the readout would not animate at all.
    const { lines } = run('tiny')
    const distinct = new Set(lines.map((l) => l.w.join(',')))
    expect(distinct.size).toBeGreaterThan(1)
  })

  it('starts from a zero bias', () => {
    expect(run('tiny').lines[0].b).toBe(0)
  })

  it('moves the weights away from their starting point', () => {
    const { lines } = run('tiny')
    expect(lines[0].w).not.toEqual(lines.at(-1)!.w)
  })
})

describe('numerical health', () => {
  it.each<DatasetName>(['tiny', 'xor'])('produces no NaN or Infinity for %s', (dataset) => {
    // The 1e-7 loss clamp exists so log(0) can't reach the output. If it is ever
    // removed, this is the test that says so.
    for (const line of run(dataset).lines) {
      expect(line.text).not.toMatch(/NaN|Infinity/)
    }
  })

  it('drives the loss down on the dataset it can fit', () => {
    const losses = run('tiny')
      .lines.filter((l) => l.kind === 'epoch')
      .map((l) => Number(/loss (\d+\.\d+)/.exec(l.text)![1]))

    expect(losses.at(-1)!).toBeLessThan(losses[0])
  })

  it('leaves the loss stuck on XOR', () => {
    // The frozen loss is what the landing copy points at, so it needs a guard.
    const losses = run('xor')
      .lines.filter((l) => l.kind === 'epoch')
      .map((l) => Number(/loss (\d+\.\d+)/.exec(l.text)![1]))

    expect(losses.at(-1)!).toBeGreaterThan(0.5)
  })
})
