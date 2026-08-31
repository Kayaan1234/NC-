// The step1 walkthrough: what happens on screen, and for how long.
//
// This file is DATA. Every word the reader sees lives in narration.mdx, in a <Beat>
// block whose id matches a scene here; walkthrough.test.ts asserts the two sets are
// exactly equal, so a typo fails the suite rather than rendering a blank caption.
// Read step0/walkthrough.ts first: this is the same arrangement, second time round.
//
// ---- What makes this one different ----
//
// step1 is a SEQUEL, and the running order is built on that. A reader arriving here
// has already watched a neuron get built, seen gradient descent, and derived binary
// cross-entropy. None of that is explained again. Every chapter instead opens by
// naming the step0 fact it is about to extend, and spends its time only on what is
// genuinely new: batching, the chain rule across a stack, and softmax.
//
// That discipline is what keeps it to sixteen minutes for a model roughly four times
// the size of step0's. The temptation is to re-derive; resist it. If a beat could
// have appeared in step0, it does not belong here.
//
// ---- The through-line ----
//
// The same pattern as step0 (formula, then the function that encodes it, then what
// the encoding cost) with one addition: SHAPES are the argument. At this size you
// cannot check the calculus by staring at it, but you can check that the only way to
// multiply two matrices and get something the shape of `weight` is the way the code
// does it. That is `layer-shapes`, and it is the chapter's point.
//
// The emotional centre is `math-absorbed`. step0's best moment was the p(1-p)
// cancellation, where doing the calculus properly made `gradient()` short. The exact
// same thing happens here at ten classes instead of two, and the beat says so
// outright. Everything downstream depends on it: it is why the output layer must be
// LINEAR (`mlp-linear`), and it is the one line of `train_mlp` worth pausing on.
//
// Durations are hand-tuned by watching, not calculated. A beat carrying a derivation
// needs noticeably longer than one carrying a sentence.

import type { Chapter, Scene } from '../walkthrough/types'
import type { Step1SourceFile } from './source'

export type Step1Chapter = 'overview' | 'matrix' | 'math' | 'layer' | 'mlp' | 'main'

/**
 * What the stage draws. Each variant maps to one branch of Step1Stage.tsx.
 *
 * Almost every one of these is a diagram the six .mdx pages already used, taken over
 * unchanged. That is deliberate: the pictures were computed rather than drawn, so
 * they were the half of those pages worth keeping, and reusing them means the
 * walkthrough looks like the rest of the site rather than like a second visual
 * language living next to it.
 *
 * `xorTransform` is the one genuinely new picture, and `moved` is its whole state:
 * false is the arrangement step0 failed on, true is the same four points after a
 * hidden layer has moved them.
 */
export type Step1Stage =
  | { kind: 'mlp' }
  | { kind: 'mlpStack' }
  | { kind: 'xorTransform'; moved?: boolean }
  | { kind: 'xorHidden' }
  | { kind: 'matrixFlat' }
  | { kind: 'matrixIndex' }
  | { kind: 'matrixOp'; op: 'bias' | 'subtract' | 'hadamard' | 'scale' | 'apply' }
  | { kind: 'activation'; fn: 'tanh' | 'relu' }
  | { kind: 'loss'; of: 'softmax' | 'crossEntropy' }
  | { kind: 'layerFlow'; pass: 'forward' | 'backward' }
  | { kind: 'miniBatch' }
  | { kind: 'mnist' }
  | { kind: 'none' }

export type Step1Scene = Scene<Step1Stage, Step1Chapter, Step1SourceFile>

// Slugs are the ones the six .mdx pages used, so every existing
// /training/step1/learn/:slug link still resolves. It now seeks to a timestamp
// instead of loading a page.
export const CHAPTERS: Chapter<Step1Chapter>[] = [
  { slug: 'overview', title: 'Stacking neurons' },
  { slug: 'matrix', title: 'matrix.hpp' },
  { slug: 'math', title: 'math.hpp' },
  { slug: 'layer', title: 'layer.hpp' },
  { slug: 'mlp', title: 'MLP.hpp' },
  { slug: 'main', title: 'main.cpp' },
]

export const SCENES: Step1Scene[] = [
  // --- Stacking neurons ----------------------------------------------------
  // Ninety seconds, and its only job is to answer "why is one neuron not enough".
  // The answer is XOR, which step0 already showed failing, so this does not re-show
  // the failure. It shows the fix.
  { id: 'overview-stack', chapter: 'overview', seconds: 22, stage: { kind: 'mlp' } },
  { id: 'overview-xor', chapter: 'overview', seconds: 24, stage: { kind: 'xorTransform' } },
  // The payoff, and the one scene in the walkthrough that genuinely moves.
  { id: 'overview-transform', chapter: 'overview', seconds: 28, stage: { kind: 'xorTransform', moved: true } },
  { id: 'overview-plan', chapter: 'overview', seconds: 16, stage: { kind: 'mlpStack' } },

  // --- matrix.hpp ----------------------------------------------------------
  // The new data structure, and why it had to appear. Kept to five beats: the flat
  // indexing is interesting but it is plumbing, and it gets one.
  { id: 'matrix-why', chapter: 'matrix', seconds: 24, stage: { kind: 'mlpStack' } },
  { id: 'matrix-flat', chapter: 'matrix', seconds: 26, stage: { kind: 'matrixFlat' } },
  {
    id: 'matrix-matmul',
    chapter: 'matrix',
    seconds: 30,
    stage: { kind: 'matrixIndex' },
    code: { kind: 'source', file: 'matrix.hpp', anchor: 'inline Matrix matmul', emphasise: ['for (int k'] },
  },
  {
    id: 'matrix-bias',
    chapter: 'matrix',
    seconds: 24,
    stage: { kind: 'matrixOp', op: 'bias' },
    code: {
      kind: 'source',
      file: 'matrix.hpp',
      anchor: 'inline Matrix& element_wise_add_',
      emphasise: ['Bias.rows != 1'],
    },
  },
  {
    // The `_` suffix convention. Worth a beat because it is the first time this
    // course cares about allocation at all.
    id: 'matrix-inplace',
    chapter: 'matrix',
    seconds: 26,
    stage: { kind: 'matrixOp', op: 'apply' },
    code: { kind: 'source', file: 'matrix.hpp', anchor: 'inline Matrix& scale_' },
  },

  // --- math.hpp ------------------------------------------------------------
  // The longest chapter, and the one that earns its length. Everything here is new:
  // step0 had one activation and one loss.
  { id: 'math-activations', chapter: 'math', seconds: 26, stage: { kind: 'activation', fn: 'tanh' } },
  {
    // The reason forward caches its OUTPUT rather than its input.
    id: 'math-deriv-trick',
    chapter: 'math',
    seconds: 30,
    stage: { kind: 'activation', fn: 'tanh' },
    code: { kind: 'source', file: 'math.hpp', anchor: 'inline double tanh_deriv' },
  },
  { id: 'math-relu', chapter: 'math', seconds: 18, stage: { kind: 'activation', fn: 'relu' } },
  {
    id: 'math-softmax',
    chapter: 'math',
    seconds: 30,
    stage: { kind: 'loss', of: 'softmax' },
    code: { kind: 'source', file: 'math.hpp', anchor: 'inline Matrix& softmax', emphasise: ['row_max'] },
  },
  { id: 'math-softmax-stability', chapter: 'math', seconds: 24, stage: { kind: 'none' } },
  {
    id: 'math-crossentropy',
    chapter: 'math',
    seconds: 28,
    stage: { kind: 'loss', of: 'crossEntropy' },
    code: { kind: 'source', file: 'math.hpp', anchor: 'inline double cross_entropy_loss' },
  },
  {
    // The moment the chapter exists for, and step0's cancellation all over again.
    id: 'math-absorbed',
    chapter: 'math',
    seconds: 34,
    stage: { kind: 'none' },
    code: {
      kind: 'source',
      file: 'math.hpp',
      anchor: 'inline Matrix cross_entropy_loss_grad',
      emphasise: ['element_wise_subtract(pred, truth)'],
    },
  },
  { id: 'math-absorbed-why', chapter: 'math', seconds: 26, stage: { kind: 'none' } },

  // --- layer.hpp -----------------------------------------------------------
  // Where the chain rule stops being a formula and starts being three lines of
  // matrix arithmetic whose shapes have only one possible arrangement.
  {
    id: 'layer-holds',
    chapter: 'layer',
    seconds: 28,
    stage: { kind: 'layerFlow', pass: 'forward' },
    code: { kind: 'source', file: 'layer.hpp', anchor: 'Layer(int fan_in', emphasise: ['weight(fan_in, fan_out, rng)'] },
  },
  {
    id: 'layer-forward',
    chapter: 'layer',
    seconds: 30,
    stage: { kind: 'layerFlow', pass: 'forward' },
    code: {
      kind: 'source',
      file: 'layer.hpp',
      anchor: 'const Matrix& forward',
      emphasise: ['matmul(input, weight, cache_output)', 'element_wise_add_', 'apply_(cache_output'],
    },
  },
  { id: 'layer-cache', chapter: 'layer', seconds: 24, stage: { kind: 'none' } },
  { id: 'layer-chain', chapter: 'layer', seconds: 32, stage: { kind: 'layerFlow', pass: 'backward' } },
  {
    id: 'layer-gradw',
    chapter: 'layer',
    seconds: 30,
    stage: { kind: 'layerFlow', pass: 'backward' },
    code: {
      kind: 'source',
      file: 'layer.hpp',
      anchor: 'Matrix backward',
      emphasise: ['transpose(cache_input)'],
    },
  },
  { id: 'layer-gradb', chapter: 'layer', seconds: 24, stage: { kind: 'none' } },
  // The chapter's argument: you cannot check the calculus by eye at this size, but
  // you can check the shapes, and only one arrangement works.
  { id: 'layer-shapes', chapter: 'layer', seconds: 28, stage: { kind: 'layerFlow', pass: 'backward' } },
  {
    id: 'layer-update',
    chapter: 'layer',
    seconds: 22,
    stage: { kind: 'none' },
    code: { kind: 'source', file: 'layer.hpp', anchor: 'Matrix& update' },
  },

  // --- MLP.hpp -------------------------------------------------------------
  // Short on purpose. Once a layer is right, a stack of them is two loops.
  {
    id: 'mlp-stack',
    chapter: 'mlp',
    seconds: 24,
    stage: { kind: 'mlpStack' },
    code: { kind: 'source', file: 'MLP.hpp', anchor: 'const Matrix& forward' },
  },
  { id: 'mlp-forward', chapter: 'mlp', seconds: 24, stage: { kind: 'mlpStack' } },
  {
    id: 'mlp-backward',
    chapter: 'mlp',
    seconds: 30,
    stage: { kind: 'mlpStack' },
    code: { kind: 'source', file: 'MLP.hpp', anchor: 'Matrix backward', emphasise: ['rbegin'] },
  },
  // Pays off math-absorbed directly: the softmax is inside the gradient, so a
  // softmax on the last layer would apply it twice.
  { id: 'mlp-linear', chapter: 'mlp', seconds: 32, stage: { kind: 'none' } },
  { id: 'mlp-gradcheck', chapter: 'mlp', seconds: 26, stage: { kind: 'none' } },

  // --- main.cpp ------------------------------------------------------------
  // Argument parsing is skipped entirely. What is left is the two datasets and the
  // loop that trains on them.
  {
    id: 'main-defaults',
    chapter: 'main',
    seconds: 26,
    stage: { kind: 'none' },
    code: { kind: 'source', file: 'main.cpp', anchor: 'void apply_defaults', emphasise: ['xor_ds ?'] },
  },
  { id: 'main-xor-works', chapter: 'main', seconds: 26, stage: { kind: 'xorHidden' } },
  { id: 'main-mnist', chapter: 'main', seconds: 28, stage: { kind: 'mnist' } },
  { id: 'main-batches', chapter: 'main', seconds: 26, stage: { kind: 'miniBatch' } },
  {
    // Everything the walkthrough has built, on one screen.
    id: 'main-loop',
    chapter: 'main',
    seconds: 32,
    stage: { kind: 'none' },
    code: {
      kind: 'source',
      file: 'main.cpp',
      anchor: 'void train_mlp',
      emphasise: ['std::shuffle', 'softmax_cross_entropy_loss_grad', 'layer.update'],
    },
  },
  { id: 'main-next', chapter: 'main', seconds: 20, stage: { kind: 'none' } },
]
