// step0 on the abstraction ladder: the same single neuron in four languages, and
// what each one decided on your behalf.
//
// This file is DATA. Every Python and NumPy snippet lives in abstraction.mdx as a
// <Snippet> with a matching id, so the build-time shiki pass highlights it and the
// voice rules in content/README.md still govern the prose. abstraction.test.ts
// checks the two sets match in both directions.
//
// The C++ cells reference the real files by anchor, so they cannot drift from the
// code that compiles. The Python cells are authored, because nothing in this repo
// implements the model in Python, and the page labels them as such.
//
// Every default asserted here was checked against a primary source on 2026-08-29:
// scikit-learn's own docs and sklearn/linear_model/_logistic.py, and PyTorch's
// torch/nn/modules/{linear,loss}.py plus the SGD docs. Where a claim is checkable
// against a version this repo pins, `provenance` says so and the test enforces it.

import type { Abstraction } from '../abstraction/types'
import type { CodeRef } from '../walkthrough/types'
import type { SourceFile } from './source'

const cpp = (
  file: SourceFile,
  anchor: string,
  emphasise?: string[],
): CodeRef<SourceFile> => ({ kind: 'source', file, anchor, ...(emphasise ? { emphasise } : {}) })

export const STEP0_ABSTRACTION: Abstraction = {
  rungs: [
    {
      id: 'sklearn',
      label: 'scikit-learn',
      blurb: 'one call does all of it',
      // Pinned in backend/requirements-worker.lock.txt; abstraction.test.ts checks
      // this version string still matches the lockfile.
      provenance: { kind: 'locked', pkg: 'scikit-learn', version: '1.9.0' },
    },
    {
      id: 'pytorch',
      label: 'PyTorch',
      blurb: 'you assemble the parts, it runs them',
      // Deliberately NOT a dependency of this repo. Adding a couple of gigabytes to
      // the worker image to serve a documentation page would be the wrong trade, so
      // these claims are read from the published source and cannot be checked here.
      provenance: {
        kind: 'cited',
        pkg: 'torch',
        version: '2.x',
        url: 'https://github.com/pytorch/pytorch/blob/main/torch/nn/modules/linear.py',
        checked: '2026-08-29',
      },
    },
    {
      id: 'numpy',
      label: 'NumPy',
      blurb: 'the maths written out, without the C++ ceremony',
      provenance: { kind: 'locked', pkg: 'numpy', version: '2.4.6' },
    },
    {
      id: 'cpp',
      label: 'C++',
      blurb: 'what you built',
      provenance: { kind: 'ours' },
    },
  ],

  concepts: [
    // --- Initialisation ----------------------------------------------------
    {
      slug: 'init',
      title: 'Initialisation',
      question: 'How each rung gets its starting weights',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-init' },
          defaults: [
            {
              name: 'starting weights',
              value: 'all zeros',
              verdict: 'differs',
              note: 'sklearn starts every coefficient at exactly 0 and gives you no way to change it. Ours starts from a gaussian scaled by one over the square root of the input size, so the sigmoid begins somewhere steep. Zeros are fine for one neuron, though on Rung 1 they would leave every hidden unit learning the same feature forever.',
            },
            {
              name: 'random_state',
              value: 'None',
              verdict: 'no-equivalent',
              note: 'Only the sag, saga and liblinear solvers touch it, so with the default solver there is nothing random to seed. Ours takes an mt19937 because it actually draws numbers.',
            },
          ],
        },
        {
          rung: 'pytorch',
          code: { kind: 'authored', snippet: 'pytorch-init' },
          defaults: [
            {
              name: 'weight',
              value: 'U(-1/√fan_in, +1/√fan_in)',
              verdict: 'differs',
              note: 'The same scale our C++ picks, drawn from a uniform rather than a gaussian. nn.Linear calls kaiming_uniform_ with a = √5, which works out to exactly those bounds. Close enough that it is easy to miss, different enough to give you different numbers.',
            },
            {
              name: 'bias',
              value: 'U(-1/√fan_in, +1/√fan_in)',
              verdict: 'differs',
              note: 'Our bias starts at exactly 0.0. PyTorch gives it a small random value as well, on the same bounds as the weights.',
            },
          ],
        },
        {
          rung: 'numpy',
          code: { kind: 'authored', snippet: 'numpy-init' },
          defaults: [
            {
              name: 'dtype',
              value: 'float64',
              verdict: 'matches',
              note: 'The same 8 byte double the C++ uses in every file. Worth knowing it is a default rather than a law, because a stray float32 somewhere changes your answers.',
            },
          ],
        },
        {
          rung: 'cpp',
          code: {
            kind: 'source',
            refs: [cpp('logistic_regression.hpp', 'explicit Node', ['const double scale'])],
          },
          defaults: [],
        },
      ],
    },

    // --- Forward pass ------------------------------------------------------
    {
      slug: 'forward',
      title: 'Forward pass',
      question: 'How each rung turns inputs into a prediction',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-forward' },
          defaults: [
            {
              name: 'decision threshold',
              value: '0.5',
              verdict: 'matches',
              note: 'predict() cuts at a half, the same place accuracy() does in main.cpp. predict_proba() hands you the probability if you would rather cut somewhere else.',
            },
            {
              name: 'fit_intercept',
              value: 'True',
              verdict: 'matches',
              note: 'You get a bias term. Our Node always has one, so there was never a decision to make.',
            },
          ],
        },
        {
          rung: 'pytorch',
          code: { kind: 'authored', snippet: 'pytorch-forward' },
          defaults: [
            {
              name: 'bias',
              value: 'True',
              verdict: 'matches',
              note: 'nn.Linear adds a bias unless you switch it off.',
            },
            {
              name: 'no sigmoid',
              value: 'raw logits out',
              verdict: 'differs',
              note: 'nn.Linear stops at the weighted sum. Our forward() runs the sigmoid too. The nonlinearity has not gone anywhere, it has moved into the loss, for the reason on the next tab.',
            },
          ],
        },
        {
          rung: 'numpy',
          code: { kind: 'authored', snippet: 'numpy-forward' },
          defaults: [
            {
              name: 'broadcasting',
              value: 'implicit',
              verdict: 'no-equivalent',
              note: 'X @ w + b adds the bias to every row at once. Our C++ loops over the samples and adds it one at a time, which is the same arithmetic with the loop written down.',
            },
          ],
        },
        {
          rung: 'cpp',
          code: {
            kind: 'source',
            refs: [
              cpp('logistic_regression.hpp', 'double forward'),
              cpp('math.hpp', 'inline double sigmoid'),
            ],
          },
          defaults: [],
        },
      ],
    },

    // --- Loss --------------------------------------------------------------
    {
      slug: 'loss',
      title: 'Loss',
      question: 'How each rung measures being wrong',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-loss' },
          defaults: [
            {
              name: 'penalty',
              value: "'l2'",
              verdict: 'differs',
              note: 'Every fit is L2 penalised, so the objective has a term pulling the weights toward zero. Our C++ minimises plain cross entropy. These two are solving different problems, and the answers differ even when everything else lines up.',
            },
            {
              name: 'C',
              value: '1.0',
              verdict: 'no-equivalent',
              note: 'The inverse of the regularisation strength, so a smaller C pulls harder. There is no knob for it in our code because there is no penalty to tune.',
            },
          ],
        },
        {
          rung: 'pytorch',
          code: { kind: 'authored', snippet: 'pytorch-loss' },
          defaults: [
            {
              name: 'log-sum-exp',
              value: 'BCEWithLogitsLoss',
              verdict: 'differs',
              note: 'Remember the clamp. Our C++ builds p, pins it inside [1e-7, 1 - 1e-7] and takes the log, so a confident wrong answer cannot produce an infinity. PyTorch never builds p at all. It stays in logit space and uses the log-sum-exp trick, which is a different answer to the same overflow problem.',
            },
            {
              name: 'reduction',
              value: "'mean'",
              verdict: 'matches',
              note: 'Averages over the batch, which is exactly what binaryLoss does when it divides by the number of samples.',
            },
          ],
        },
        {
          rung: 'numpy',
          code: { kind: 'authored', snippet: 'numpy-loss' },
          defaults: [
            {
              name: 'overflow guard',
              value: 'none',
              verdict: 'no-equivalent',
              note: 'Nothing here stops you handing log a zero. You add the clamp yourself, the same way math.hpp does, and if you forget you get a silent nan that poisons the epoch average.',
            },
          ],
        },
        {
          rung: 'cpp',
          code: {
            kind: 'source',
            refs: [cpp('logistic_regression.hpp', 'double binaryLoss', ['std::clamp'])],
          },
          defaults: [],
        },
      ],
    },

    // --- Optimiser ---------------------------------------------------------
    // The headline. This is where the one-liner turns out to be running an
    // algorithm the reader never derived.
    {
      slug: 'optimiser',
      title: 'Optimiser',
      question: 'How each rung improves the weights',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-optimiser' },
          defaults: [
            {
              name: 'solver',
              value: "'lbfgs'",
              verdict: 'differs',
              note: 'A quasi-Newton method. It builds an approximation of the curvature of the loss and jumps toward where it thinks the minimum is. The gradient descent you derived and wrote out by hand is not what runs here.',
            },
            {
              name: 'learning rate',
              value: 'no such parameter',
              verdict: 'no-equivalent',
              note: 'lbfgs chooses its own step size by line search, so there is no lr to pass. Everything you learned about setting it too high or too low simply does not apply to this call.',
            },
          ],
        },
        {
          rung: 'pytorch',
          code: { kind: 'authored', snippet: 'pytorch-optimiser' },
          defaults: [
            {
              name: 'momentum',
              value: '0',
              verdict: 'matches',
              note: 'Off by default, so the update really is w -= lr * grad. That is the line you wrote in update(), running unchanged.',
            },
            {
              name: 'weight_decay',
              value: '0',
              verdict: 'matches',
              note: 'No L2 penalty unless you ask for one. So where sklearn quietly changed the objective, PyTorch leaves it exactly as you derived it.',
            },
            {
              name: 'nesterov',
              value: 'False',
              verdict: 'matches',
              note: 'Off, so nothing clever is happening to the step you take.',
            },
          ],
        },
        {
          rung: 'numpy',
          code: { kind: 'authored', snippet: 'numpy-optimiser' },
          defaults: [],
        },
        {
          rung: 'cpp',
          code: {
            kind: 'source',
            refs: [
              cpp('logistic_regression.hpp', 'Grad gradient', ['const double error']),
              cpp('logistic_regression.hpp', 'void update'),
            ],
          },
          defaults: [],
        },
      ],
    },

    // --- Stopping ----------------------------------------------------------
    {
      slug: 'stopping',
      title: 'Stopping',
      question: 'How each rung decides it has finished',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-stopping' },
          defaults: [
            {
              name: 'tol',
              value: '1e-4',
              verdict: 'differs',
              note: 'It stops once the gradient gets small enough, so you cannot tell in advance how many steps it will take.',
            },
            {
              name: 'max_iter',
              value: '100',
              verdict: 'differs',
              note: 'If it has not converged by a hundred iterations it gives up and warns you. Our loop runs its full 500 epochs whatever happens, which is why you can watch the loss column the whole way down.',
            },
          ],
        },
        {
          rung: 'pytorch',
          code: { kind: 'authored', snippet: 'pytorch-stopping' },
          defaults: [
            {
              name: 'the loop',
              value: 'yours to write',
              verdict: 'matches',
              note: 'PyTorch has no opinion about when you are done. You write the epoch loop yourself, the same as main.cpp does.',
            },
          ],
        },
        {
          rung: 'numpy',
          code: { kind: 'authored', snippet: 'numpy-stopping' },
          defaults: [],
        },
        {
          rung: 'cpp',
          code: {
            kind: 'source',
            refs: [cpp('main.cpp', 'void train', ['node.gradient', 'node.update'])],
          },
          defaults: [],
        },
      ],
    },
  ],
}
