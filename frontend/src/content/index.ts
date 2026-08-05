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
  // Being written a file at a time, in dependency order (matrix before layer,
  // because a layer is two matrices). Sections are added as each page lands; a
  // partial flow is a valid flow, and the last page's Next is "Start training".
  step1: {
    name: 'Multilayer Perceptron',
    sections: [
      { slug: 'overview', title: 'Overview', Body: step1Overview },
      { slug: 'matrix', title: 'matrix.hpp', Body: step1Matrix },
    ],
  },
}

export function getModelContent(id: string | undefined): ModelContent | undefined {
  return id ? MODEL_CONTENT[id] : undefined
}

export function hasContent(id: string): boolean {
  return id in MODEL_CONTENT
}
