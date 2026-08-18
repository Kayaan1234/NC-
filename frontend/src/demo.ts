// The landing page's in-browser training run: a TypeScript port of the Rung 0
// neuron, so a logged-out visitor can watch one train before they have an account.
//
// This is a port, not a simulation. Every number below comes out of the same
// arithmetic as backend/services/Step0/logistic_regression.hpp — sigmoid forward,
// mean-normalised batch gradient, the same 1e-7 loss clamp, the same
// 1/sqrt(fan_in) init scale — and the lines are formatted to match what
// Step0/main.cpp actually prints, down to the column widths. Nothing here queues a
// job, calls the API, or needs a session.
//
// What it deliberately does NOT reproduce: std::mt19937. A JS PRNG draws different
// initial weights, so the loss values differ from a real server-side run even
// though the trajectory and the endpoint don't. The landing copy says "the same
// arithmetic, in your browser" and never claims the numbers match a real job.

export type DatasetName = 'tiny' | 'xor'

type Dataset = { X: number[][]; y: number[] }

// Copied from make_tiny() / make_xor() in Step0/main.cpp. `blobs` is left out: it
// is 200 random 4-D points, which says nothing to someone reading a log.
const DATASETS: Record<DatasetName, Dataset> = {
  // Linearly separable — a straight line splits it, which is all a neuron can do.
  tiny: { X: [[1, 2], [-1, -1.5], [2, -0.5]], y: [1, 0, 1] },
  // Not linearly separable. This is the run that fails, and the reason Rung 1 exists.
  xor: { X: [[0, 0], [0, 1], [1, 0], [1, 1]], y: [0, 1, 1, 0] },
}

// The defaults the real CLI uses, so the header line reads exactly as it would
// after `nn --dataset tiny`. 500 epochs printing every epochs/10 gives ten
// progress lines plus the last — the height the terminal block is sized for.
const LR = 0.5
const EPOCHS = 500
const SEED = 42

// --- math.hpp ---------------------------------------------------------------

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x))

const dot = (a: number[], b: number[]) => a.reduce((t, v, i) => t + v * b[i], 0)

// --- deterministic init -----------------------------------------------------

// mulberry32 + Box–Muller. Seeded so every visitor sees the same run and "Run
// again" reproduces it: a demo whose numbers changed on each render would look
// like a random-number generator rather than a training run.
function gaussians(seed: number, n: number, scale: number): number[] {
  let s = seed
  const next = () => {
    s = (s + 0x6d2b79f5) | 0
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  const out: number[] = []
  while (out.length < n) {
    // u1 is clamped away from 0 because log(0) is -Infinity.
    const u1 = Math.max(next(), Number.EPSILON)
    const u2 = next()
    out.push(Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2) * scale)
  }
  return out.slice(0, n)
}

// --- logistic_regression.hpp ------------------------------------------------

function loss(w: number[], b: number, d: Dataset): number {
  const eps = 1e-7
  let total = 0
  for (let i = 0; i < d.X.length; i++) {
    const p = Math.min(Math.max(sigmoid(dot(d.X[i], w) + b), eps), 1 - eps)
    total += d.y[i] * Math.log(p) + (1 - d.y[i]) * Math.log(1 - p)
  }
  return -total / d.y.length
}

// Note the `>= 0.5` threshold, matching accuracy() in main.cpp. It matters on XOR:
// the weights collapse to ~0 there, so every prediction sits on the boundary and
// the tie-break decides the number. That is why the landing copy talks about the
// frozen loss and never quotes an XOR accuracy.
function accuracy(w: number[], b: number, d: Dataset): number {
  let correct = 0
  for (let i = 0; i < d.X.length; i++) {
    if ((sigmoid(dot(d.X[i], w) + b) >= 0.5 ? 1 : 0) === d.y[i]) correct++
  }
  return correct / d.y.length
}

// --- output formatting ------------------------------------------------------

// std::fixed << std::setprecision(4)
const fixed4 = (x: number) => x.toFixed(4)

// std::defaultfloat << std::setprecision(8) — up to 8 significant digits with
// trailing zeros dropped, which is how the RESULT line's numbers print.
const sig8 = (x: number) => String(Number(x.toPrecision(8)))

export type LineKind = 'header' | 'epoch' | 'final' | 'result'

export type LogLine = {
  kind: LineKind
  text: string
  // The model's state as of this line, so the weights readout above the log can
  // advance in step with it rather than jumping to the final value.
  w: number[]
  b: number
}

export type Run = {
  dataset: DatasetName
  lines: LogLine[]
  /** Whether the neuron actually fitted the data. False on XOR — see below. */
  solved: boolean
}

/**
 * Train the neuron and return the whole log at once.
 *
 * The run is a few thousand float operations and completes in well under a
 * millisecond, so it is computed synchronously and up front; the component then
 * reveals the lines on a timer. Separating the arithmetic from the pacing keeps
 * the reduced-motion path (show everything immediately) from needing its own
 * code path through the maths.
 */
export function run(dataset: DatasetName): Run {
  const d = DATASETS[dataset]
  const n = d.X[0].length
  const w = gaussians(SEED, n, 1 / Math.sqrt(n))
  let b = 0

  const lines: LogLine[] = []
  const snapshot = (kind: LineKind, text: string) =>
    lines.push({ kind, text, w: [...w], b })

  snapshot(
    'header',
    `=== training: dataset=${dataset} lr=${LR} epochs=${EPOCHS} ` +
      `samples=${d.X.length} features=${n} seed=${SEED} ===`,
  )

  const every = Math.max(1, Math.floor(EPOCHS / 10))

  for (let e = 0; e < EPOCHS; e++) {
    const N = d.X.length
    const gw = new Array<number>(n).fill(0)
    let gb = 0
    for (let i = 0; i < N; i++) {
      const err = sigmoid(dot(d.X[i], w) + b) - d.y[i]
      for (let j = 0; j < n; j++) gw[j] += err * d.X[i][j]
      gb += err
    }
    for (let j = 0; j < n; j++) w[j] -= LR * (gw[j] / N)
    b -= LR * (gb / N)

    if (e % every === 0 || e === EPOCHS - 1) {
      snapshot(
        'epoch',
        `epoch ${String(e).padStart(4)}  loss ${fixed4(loss(w, b, d))}` +
          `  acc ${fixed4(accuracy(w, b, d) * 100)}%`,
      )
    }
  }

  const finalLoss = loss(w, b, d)
  const finalAcc = accuracy(w, b, d)

  snapshot('final', `final accuracy ${fixed4(finalAcc * 100)}%`)
  snapshot(
    'result',
    `RESULT {"dataset":"${dataset}","learning_rate":${LR},"epochs":${EPOCHS},` +
      `"samples":${d.X.length},"features":${n},"seed":${SEED},` +
      `"final_loss":${sig8(finalLoss)},"final_accuracy":${sig8(finalAcc)},` +
      `"diverged":false}`,
  )

  // "Did it fit the data" is the one question with a stable answer. Testing the
  // loss instead would need a magic constant, and testing the XOR *accuracy* is
  // worse than useless: the weights collapse to ~0 there, so every prediction sits
  // exactly on the 0.5 threshold and the figure is decided by float residue of
  // order 1e-9 — it reads 75% here and could read 50% elsewhere. Either way it is
  // short of 1, which is the only thing the caller needs to know.
  return { dataset, lines, solved: finalAcc >= 1 }
}
