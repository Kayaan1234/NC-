// step1 on the abstraction ladder: the same MLP in four languages, and what each
// one decided on your behalf.
//
// This file is DATA. Every Python and NumPy snippet lives in abstraction.mdx as a
// <Snippet> with a matching id, so the build-time shiki pass highlights it and the
// voice rules in content/README.md still govern the prose. abstraction.test.ts
// checks the two sets match in both directions.
//
// Read step0/abstraction.ts first; this is the same arrangement for a bigger model.
// What is different is that at this size the gap between the rungs is much wider.
// step0's one-liner and its C++ at least agreed about what they were minimising.
// MLPClassifier() defaults to Adam, an L2 penalty, a hundred hidden units and a
// hidden batch size, so four defaults you never typed have changed the optimiser,
// the objective, the architecture and the data ordering.
//
// Every sklearn default asserted here was read on 2026-08-30 out of the INSTALLED
// scikit-learn 1.9.0, the version backend/requirements-worker.lock.txt pins, using
// inspect.signature on MLPClassifier.__init__ and the source of _init_coef and
// _fit_stochastic in sklearn/neural_network/_multilayer_perceptron.py. Not recalled,
// and not read off a docs page for some other version. PyTorch is not installed
// anywhere in this repo, so its claims are cited and carry the date instead.
//
// The one to make sure survives any edit is `pytorch/loss`. nn.CrossEntropyLoss
// takes logits and applies log_softmax itself, which is the SAME absorbed softmax
// the walkthrough spends its longest beat on, and the same reason MLP.hpp insists
// the output layer be LINEAR. A reader who gets that has understood something real
// about PyTorch, from having written the C++.

import type { Abstraction } from '../abstraction/types'
import type { CodeRef } from '../walkthrough/types'
import type { Step1SourceFile } from './source'

const cpp = (
  file: Step1SourceFile,
  anchor: string,
  emphasise?: string[],
): CodeRef<Step1SourceFile> => ({
  kind: 'source',
  file,
  anchor,
  ...(emphasise ? { emphasise } : {}),
})

export const STEP1_ABSTRACTION: Abstraction = {
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
        url: 'https://github.com/pytorch/pytorch/blob/main/torch/nn/modules/loss.py',
        checked: '2026-08-30',
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
      question: 'How each rung decides the shape of the network and its starting weights',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-init' },
          defaults: [
            {
              name: 'hidden_layer_sizes',
              value: '(100,)',
              verdict: 'differs',
              note: 'One hidden layer of a hundred units, chosen before it has seen your data. The C++ makes you say, and its own defaults are eight for XOR and thirty two for MNIST, both far smaller.',
            },
            {
              name: 'starting weights',
              value: 'U(±√(6/(fan_in+fan_out)))',
              verdict: 'differs',
              note: 'Glorot initialisation, uniform, and the bound uses both the input and the output width. Ours is a gaussian scaled by one over the square root of the input width only. Same instinct, different distribution and a different number in the denominator.',
            },
            {
              name: 'starting bias',
              value: 'U(±√(6/(fan_in+fan_out)))',
              verdict: 'differs',
              note: 'Every bias gets a small random value on those same bounds. Ours start at exactly zero, which is what Matrix(1, fan_out) gives you.',
            },
            {
              name: 'activation',
              value: "'relu'",
              verdict: 'matches',
              note: 'The same activation main.cpp picks for MNIST, and for the same reason: it is cheap and it does not squash the gradient. Worth knowing it is a default you agreed to rather than a decision you made.',
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
              note: 'The same scale our C++ picks, drawn from a uniform rather than a gaussian. nn.Linear calls kaiming_uniform_ with a = √5, which works out to exactly those bounds.',
            },
            {
              name: 'bias',
              value: 'U(-1/√fan_in, +1/√fan_in)',
              verdict: 'differs',
              note: 'Ours starts at zero. PyTorch gives it a small random value too, on the same bounds as the weights.',
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
            refs: [
              cpp('layer.hpp', 'Layer(int fan_in', ['weight(fan_in, fan_out, rng)']),
              cpp('matrix.hpp', 'void randomise', ['scale']),
            ],
          },
          defaults: [],
        },
      ],
    },

    // --- Forward pass ------------------------------------------------------
    {
      slug: 'forward',
      title: 'Forward pass',
      question: 'How each rung pushes a batch through the stack',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-forward' },
          defaults: [
            {
              name: 'output activation',
              value: 'softmax, chosen for you',
              verdict: 'differs',
              note: 'It looks at your labels, sees more than two classes, and picks softmax. With two classes it picks a logistic instead. There is no argument for this, and no way to see the logits underneath.',
            },
            {
              name: 'the forward pass itself',
              value: 'not exposed',
              verdict: 'no-equivalent',
              note: 'predict_proba runs the whole network and hands back probabilities. Nothing lets you stop halfway and look at a hidden layer, which is exactly what our forward returns a reference to.',
            },
          ],
        },
        {
          rung: 'pytorch',
          code: { kind: 'authored', snippet: 'pytorch-forward' },
          defaults: [
            {
              name: 'nn.Sequential order',
              value: 'exactly what you listed',
              verdict: 'matches',
              note: 'It calls each module in the order you wrote them and feeds each output to the next, which is the loop in MLP::forward with a nicer face on it.',
            },
          ],
        },
        {
          rung: 'numpy',
          code: { kind: 'authored', snippet: 'numpy-forward' },
          defaults: [
            {
              name: '@ broadcasting',
              value: 'bias added to every row',
              verdict: 'matches',
              note: 'Writing X @ W + b broadcasts the bias row down the batch on its own. That is element_wise_add_ and its check that the bias has exactly one row.',
            },
          ],
        },
        {
          rung: 'cpp',
          code: {
            kind: 'source',
            refs: [
              cpp('MLP.hpp', 'const Matrix& forward'),
              cpp('layer.hpp', 'const Matrix& forward', ['apply_(cache_output']),
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
      question: 'What each rung is actually minimising',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-loss' },
          defaults: [
            {
              name: 'alpha',
              value: '0.0001',
              verdict: 'no-equivalent',
              note: 'An L2 penalty on every weight, on by default. So the thing being minimised is the cross entropy plus a term about weight size, and our C++ has no concept of that at all. This is the same trap step0 had with penalty="l2": the two rungs are not minimising the same function.',
            },
            {
              name: 'loss function',
              value: 'log loss, fixed',
              verdict: 'matches',
              note: 'It is the cross entropy you derived, which is the good news. The bad news is there is no argument to change it, so if you wanted a different objective you would be reaching for a different class.',
            },
          ],
        },
        {
          rung: 'pytorch',
          code: { kind: 'authored', snippet: 'pytorch-loss' },
          defaults: [
            {
              name: 'expects logits',
              value: 'log_softmax applied inside',
              verdict: 'matches',
              note: 'This is the whole of chapter three showing up in a library. CrossEntropyLoss wants the raw scores and does the softmax itself, so the gradient it hands back is p minus y, and that is precisely why MLP.hpp refuses to let the last layer be anything but LINEAR. Put a softmax before it and you have applied one twice.',
            },
            {
              name: 'reduction',
              value: "'mean'",
              verdict: 'matches',
              note: 'Averages over the batch, the same divide by pred.rows that cross_entropy_loss_grad does.',
            },
            {
              name: 'label_smoothing',
              value: '0.0',
              verdict: 'no-equivalent',
              note: 'Off by default, and it quietly changes the targets when you turn it on. Nothing in our C++ has a knob like it.',
            },
          ],
        },
        {
          rung: 'numpy',
          code: { kind: 'authored', snippet: 'numpy-loss' },
          defaults: [
            {
              name: 'np.max(axis=1)',
              value: 'you write it yourself',
              verdict: 'matches',
              note: 'Nothing subtracts the row maximum for you here, so you write the line, the same as softmax() in math.hpp does.',
            },
          ],
        },
        {
          rung: 'cpp',
          code: {
            kind: 'source',
            refs: [
              cpp('math.hpp', 'inline Matrix& softmax', ['row_max']),
              cpp('math.hpp', 'inline double cross_entropy_loss'),
            ],
          },
          defaults: [],
        },
      ],
    },

    // --- Backward pass -----------------------------------------------------
    {
      slug: 'backward',
      title: 'Backward pass',
      question: 'How each rung gets the gradients',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-backward' },
          defaults: [
            {
              name: 'verbose',
              value: 'False',
              verdict: 'differs',
              note: 'There is no backward pass to call and nothing to inspect while it runs. Even the loss is silent unless you ask, where our train_mlp prints it ten times over the run whether you asked or not.',
            },
          ],
        },
        {
          rung: 'pytorch',
          code: { kind: 'authored', snippet: 'pytorch-backward' },
          defaults: [
            {
              name: 'gradient accumulation',
              value: 'grads ADD, they do not replace',
              verdict: 'differs',
              note: 'Call backward twice without clearing and you get the sum of both. That is why every PyTorch loop has a zero_grad in it. Our Layer::backward assigns grad_weight outright each time, so there is nothing to clear and no way to forget.',
            },
            {
              name: 'create_graph',
              value: 'False',
              verdict: 'no-equivalent',
              note: 'It builds a graph of your forward pass and differentiates it, which is the part we did by hand. Ours has one chain rule, written once, for the one architecture it supports.',
            },
          ],
        },
        {
          rung: 'numpy',
          code: { kind: 'authored', snippet: 'numpy-backward' },
          defaults: [
            {
              name: '.T',
              value: 'a view, not a copy',
              verdict: 'differs',
              note: 'NumPy transposes by relabelling the strides and copies nothing. Our transpose() builds a whole new Matrix, which is simpler to read and more work to run.',
            },
          ],
        },
        {
          rung: 'cpp',
          code: {
            kind: 'source',
            refs: [
              cpp('MLP.hpp', 'Matrix backward', ['rbegin']),
              cpp('layer.hpp', 'Matrix backward', ['transpose(cache_input)']),
            ],
          },
          defaults: [],
        },
      ],
    },

    // --- The training loop -------------------------------------------------
    {
      slug: 'training-loop',
      title: 'Training',
      question: 'What actually runs when you say fit',
      cells: [
        {
          rung: 'sklearn',
          code: { kind: 'authored', snippet: 'sklearn-training-loop' },
          defaults: [
            {
              name: 'solver',
              value: "'adam'",
              verdict: 'differs',
              note: 'The big one. Adam keeps a running average of the gradient and of its square, per parameter, and uses both to set a per parameter step size. That is a genuinely different algorithm from the one you derived, and it is what runs unless you say otherwise.',
            },
            {
              name: 'learning_rate_init',
              value: '0.001',
              verdict: 'differs',
              note: 'Five hundred times smaller than the half main.cpp uses for XOR, and a hundredth of the tenth it uses for MNIST. Adam wants a small step because it scales the step itself.',
            },
            {
              name: 'max_iter',
              value: '200',
              verdict: 'differs',
              note: 'Two hundred passes over the data, then it stops and warns you if it has not converged. Ours does two thousand for XOR and fifteen for MNIST, both because somebody chose them for that dataset.',
            },
            {
              name: 'batch_size',
              value: "'auto'",
              verdict: 'differs',
              note: 'Which means min(200, n_samples). On the ten thousand MNIST rows main.cpp loads that is batches of two hundred rather than the sixty four it uses, so the number of updates per epoch differs by a factor of three.',
            },
            {
              name: 'shuffle',
              value: 'True',
              verdict: 'matches',
              note: 'It reshuffles every epoch, which is exactly where main.cpp puts its std::shuffle. Getting this one wrong is a real bug, and both of them get it right.',
            },
          ],
        },
        {
          rung: 'pytorch',
          code: { kind: 'authored', snippet: 'pytorch-training-loop' },
          defaults: [
            {
              name: 'momentum',
              value: '0',
              verdict: 'matches',
              note: 'With this at zero, optim.SGD does w -= lr * w.grad and nothing else, which is Layer::update line for line. The defaults here really are your update rule.',
            },
            {
              name: 'weight_decay',
              value: '0',
              verdict: 'matches',
              note: 'No penalty term unless you ask, so unlike MLPClassifier it is minimising the same objective you are.',
            },
            {
              name: 'the loop itself',
              value: 'yours to write',
              verdict: 'no-equivalent',
              note: 'Epochs, batching and shuffling are all things you write out, usually with a DataLoader. PyTorch hands you the pieces and leaves the shape of train_mlp up to you.',
            },
          ],
        },
        {
          rung: 'numpy',
          code: { kind: 'authored', snippet: 'numpy-training-loop' },
          defaults: [
            {
              name: 'rng.permutation',
              value: 'you seed it or you do not',
              verdict: 'differs',
              note: 'Leave the seed out and every run shuffles differently, so two runs disagree and you cannot tell a real improvement from luck. main.cpp takes a --seed and threads one mt19937 through everything.',
            },
          ],
        },
        {
          rung: 'cpp',
          code: {
            kind: 'source',
            refs: [
              cpp('main.cpp', 'void train_mlp', ['std::shuffle', 'softmax_cross_entropy_loss_grad']),
              cpp('layer.hpp', 'Matrix& update'),
            ],
          },
          defaults: [],
        },
      ],
    },
  ],
}
