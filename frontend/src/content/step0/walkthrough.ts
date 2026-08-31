// The step0 walkthrough: what happens on screen, and for how long.
//
// This file is DATA. Every word the reader sees lives in narration.mdx, in a <Beat>
// block whose id matches a scene here; walkthrough.test.ts asserts the two sets are
// exactly equal, so a typo fails the suite rather than rendering a blank caption.
//
// The through-line, and the reason the ordering is what it is: this site teaches the
// maths first, then how that maths becomes C++. So the pattern repeats — state the
// formula, then show the function that encodes it, then say what the encoding cost
// or bought. The single best instance is the p(1-p) cancellation in chapter three,
// where doing the calculus properly is what makes `gradient()` short.
//
// It is deliberately NOT an exhaustive tour of the source. The full code is linked
// on GitHub and the last beat points at it; this builds the picture that makes
// reading it worthwhile. Detail that serves no mathematical point (the argument
// order of binaryLoss vs gradient, the numerically-stable sigmoid the file does not
// ship) is left out on purpose, not forgotten.
//
// Durations are hand-tuned by watching, not calculated. The rule of thumb that
// survived: a beat carrying a KaTeX derivation needs noticeably longer than one
// carrying a sentence, because the reader has to parse symbols rather than skim.

import type { Chapter, Scene } from '../walkthrough/types'
import type { SourceFile } from './source'

export type Step0Chapter = 'overview' | 'math' | 'logistic_regression' | 'main'

/**
 * What the stage draws. Each variant maps to one branch of Stage.tsx.
 *
 * `neuron.reveal` is the "construction" the walkthrough exists for: the parts of a
 * neuron arrive one at a time rather than all at once.
 */
export type Step0Stage =
  | { kind: 'neuron'; reveal: 'inputs' | 'weights' | 'sum' | 'bias' | 'sigmoid' | 'all' }
  | { kind: 'sigmoid'; derivative?: boolean }
  | { kind: 'bceLoss' }
  | { kind: 'learningRate' }
  | { kind: 'xor'; boundary?: boolean }
  | { kind: 'training'; dataset: 'tiny' | 'xor' }
  | { kind: 'none' }

export type Step0Scene = Scene<Step0Stage, Step0Chapter, SourceFile>

// Slugs are the ones the MDX pages used, so every existing
// /training/step0/learn/:slug link still resolves — it now seeks to a timestamp
// instead of loading a page.
export const CHAPTERS: Chapter<Step0Chapter>[] = [
  { slug: 'overview', title: 'A neuron' },
  { slug: 'math', title: 'math.hpp' },
  { slug: 'logistic_regression', title: 'logistic_regression.hpp' },
  { slug: 'main', title: 'main.cpp' },
]

export const SCENES: Step0Scene[] = [
  // --- A neuron ------------------------------------------------------------
  // Built one piece at a time. Nothing here is code yet: the point is that the
  // reader should be able to draw the object before being shown a struct.
  { id: 'overview-inputs', chapter: 'overview', seconds: 14, stage: { kind: 'neuron', reveal: 'inputs' } },
  { id: 'overview-weights', chapter: 'overview', seconds: 16, stage: { kind: 'neuron', reveal: 'weights' } },
  { id: 'overview-sum', chapter: 'overview', seconds: 14, stage: { kind: 'neuron', reveal: 'sum' } },
  { id: 'overview-bias', chapter: 'overview', seconds: 12, stage: { kind: 'neuron', reveal: 'bias' } },
  { id: 'overview-sigmoid', chapter: 'overview', seconds: 18, stage: { kind: 'neuron', reveal: 'sigmoid' } },
  { id: 'overview-why-nonlinear', chapter: 'overview', seconds: 24, stage: { kind: 'neuron', reveal: 'all' } },
  { id: 'overview-plan', chapter: 'overview', seconds: 14, stage: { kind: 'neuron', reveal: 'all' } },

  // --- math.hpp ------------------------------------------------------------
  // Formula, then the function that encodes it. Twice.
  { id: 'math-sigmoid-formula', chapter: 'math', seconds: 20, stage: { kind: 'sigmoid' } },
  {
    id: 'math-sigmoid-code',
    chapter: 'math',
    seconds: 22,
    stage: { kind: 'sigmoid' },
    code: { kind: 'source', file: 'math.hpp', anchor: 'inline double sigmoid' },
  },
  {
    id: 'math-sigmoid-derivative',
    chapter: 'math',
    seconds: 26,
    stage: { kind: 'sigmoid', derivative: true },
  },
  { id: 'math-dot-formula', chapter: 'math', seconds: 18, stage: { kind: 'neuron', reveal: 'sum' } },
  {
    // On-mission: the gap between knowing the library call and knowing the loop.
    id: 'math-dot-numpy',
    chapter: 'math',
    seconds: 18,
    stage: { kind: 'neuron', reveal: 'sum' },
    code: {
      kind: 'aside',
      lang: 'python',
      code: 'np.dot(a, b)',
      note: 'NumPy, for comparison — not part of this project',
    },
  },
  {
    id: 'math-dot-code',
    chapter: 'math',
    seconds: 24,
    stage: { kind: 'neuron', reveal: 'sum' },
    code: { kind: 'source', file: 'math.hpp', anchor: 'inline double dot' },
  },

  // --- logistic_regression.hpp ---------------------------------------------
  {
    id: 'logreg-init',
    chapter: 'logistic_regression',
    seconds: 26,
    stage: { kind: 'sigmoid' },
    code: {
      kind: 'source',
      file: 'logistic_regression.hpp',
      anchor: 'explicit Node',
      emphasise: ['const double scale'],
    },
  },
  {
    id: 'logreg-forward',
    chapter: 'logistic_regression',
    seconds: 22,
    stage: { kind: 'neuron', reveal: 'all' },
    code: { kind: 'source', file: 'logistic_regression.hpp', anchor: 'double forward' },
  },
  { id: 'logreg-loss-math', chapter: 'logistic_regression', seconds: 26, stage: { kind: 'bceLoss' } },
  {
    id: 'logreg-loss-clamp',
    chapter: 'logistic_regression',
    seconds: 22,
    stage: { kind: 'bceLoss' },
    code: {
      kind: 'source',
      file: 'logistic_regression.hpp',
      anchor: 'double binaryLoss',
      emphasise: ['std::clamp'],
    },
  },
  { id: 'logreg-derivative', chapter: 'logistic_regression', seconds: 28, stage: { kind: 'none' } },
  // The moment the chapter exists for.
  { id: 'logreg-cancellation', chapter: 'logistic_regression', seconds: 32, stage: { kind: 'none' } },
  {
    id: 'logreg-gradient-code',
    chapter: 'logistic_regression',
    seconds: 30,
    stage: { kind: 'none' },
    code: {
      kind: 'source',
      file: 'logistic_regression.hpp',
      anchor: 'Grad gradient',
      emphasise: ['const double error'],
    },
  },
  {
    id: 'logreg-update',
    chapter: 'logistic_regression',
    seconds: 22,
    stage: { kind: 'none' },
    code: { kind: 'source', file: 'logistic_regression.hpp', anchor: 'void update' },
  },
  { id: 'logreg-learning-rate', chapter: 'logistic_regression', seconds: 24, stage: { kind: 'learningRate' } },

  // --- main.cpp ------------------------------------------------------------
  {
    id: 'main-epoch',
    chapter: 'main',
    seconds: 24,
    stage: { kind: 'neuron', reveal: 'all' },
    code: {
      kind: 'source',
      file: 'main.cpp',
      anchor: 'void train',
      emphasise: ['node.gradient', 'node.update'],
    },
  },
  // Driven by demo.ts — the boundary moves because the weights moved.
  { id: 'main-training-tiny', chapter: 'main', seconds: 34, stage: { kind: 'training', dataset: 'tiny' } },
  {
    id: 'main-accuracy',
    chapter: 'main',
    seconds: 18,
    stage: { kind: 'training', dataset: 'tiny' },
    code: { kind: 'source', file: 'main.cpp', anchor: 'double accuracy' },
  },
  { id: 'main-xor-points', chapter: 'main', seconds: 22, stage: { kind: 'xor' } },
  { id: 'main-xor-boundary', chapter: 'main', seconds: 30, stage: { kind: 'xor', boundary: true } },
  { id: 'main-xor-training', chapter: 'main', seconds: 28, stage: { kind: 'training', dataset: 'xor' } },
  { id: 'main-next', chapter: 'main', seconds: 24, stage: { kind: 'none' } },
]
