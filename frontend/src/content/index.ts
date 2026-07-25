// Registry of authored "learn" content, keyed by backend model_id (the same id the
// menu links to and the training page reads from the URL). A model with no entry
// here simply has no learn flow: its menu card links straight to training. Adding a
// model's explanation is one entry here plus its .mdx pages — see content/README.md.

import type { ModelContent } from './types'
import step0Overview from './step0/1-overview.mdx'
import step0Logreg from './step0/2-math.mdx'

export const MODEL_CONTENT: Record<string, ModelContent> = {
  step0: {
    name: 'Single Neuron (Logistic Regression)',
    sections: [
      { slug: 'overview', title: 'Overview', Body: step0Overview },
      { slug: 'math', title: 'math.hpp', Body: step0Logreg },
    ],
  },
}

export function getModelContent(id: string | undefined): ModelContent | undefined {
  return id ? MODEL_CONTENT[id] : undefined
}

export function hasContent(id: string): boolean {
  return id in MODEL_CONTENT
}
