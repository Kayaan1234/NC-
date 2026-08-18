// Registry of authored "learn" content, keyed by backend model_id (the same id the
// menu links to and the training page reads from the URL). A model with no entry
// here simply has no learn flow: its menu card links straight to training. Adding a
// model's explanation is one entry here plus its .mdx pages — see content/README.md.

import type { ModelContent } from './types'
import step0Overview from './step0/1-overview.mdx'
import step0Math from './step0/2-math.mdx'
import step0Logreg from './step0/3-logistic_regression.mdx'
import step0Main from './step0/4-train-loop_and_the_data.mdx'
import step1Overview from './step1/1-overview.mdx'
import step1Matrix from './step1/2-matrix.mdx'
import step1Math from './step1/3-math.mdx'
import step1Layer from './step1/4-layer.mdx'
import step1Mlp from './step1/5-mlp.mdx'
import step1Main from './step1/6-main.mdx'

export const MODEL_CONTENT: Record<string, ModelContent> = {
  step0: {
    name: 'Single Neuron (Logistic Regression)',
    sections: [
      { slug: 'overview', title: 'Overview', Body: step0Overview },
      { slug: 'math', title: 'math.hpp', Body: step0Math },
      { slug: 'logistic_regression', title: 'logistic_regression.hpp', Body: step0Logreg },
      { slug: 'main', title: 'main.cpp', Body: step0Main },
    ],
  },
  // In dependency order (matrix before layer, because a layer is two matrices;
  // layer before MLP, because an MLP is a stack of layers). grad_check.hpp has
  // no page of its own, matching step0, where it also ships in the source and is
  // covered in a paragraph rather than a chapter — see the MLP page.
  step1: {
    name: 'Multilayer Perceptron',
    sections: [
      { slug: 'overview', title: 'Overview', Body: step1Overview },
      { slug: 'matrix', title: 'matrix.hpp', Body: step1Matrix },
      { slug: 'math', title: 'math.hpp', Body: step1Math },
      { slug: 'layer', title: 'layer.hpp', Body: step1Layer },
      { slug: 'mlp', title: 'MLP.hpp', Body: step1Mlp },
      { slug: 'main', title: 'main.cpp', Body: step1Main },
    ],
  },
}

export function getModelContent(id: string | undefined): ModelContent | undefined {
  return id ? MODEL_CONTENT[id] : undefined
}

export function hasContent(id: string): boolean {
  return id in MODEL_CONTENT
}
