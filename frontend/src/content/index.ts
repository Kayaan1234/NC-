// Registry of authored "learn" content, keyed by backend model_id (the same id the
// menu links to and the training page reads from the URL). A model with no entry
// here simply has no learn flow: its menu card links straight to training.
//
// Two shapes, picked per model — see types.ts. step0 is a narrated walkthrough
// (one timeline, chapters that seek); step1 is a sequence of .mdx pages. Adding
// either is one entry here plus its content files — see content/README.md.

import type { ModelContent } from './types'
import { CHAPTERS as step0Chapters, SCENES as step0Scenes } from './step0/walkthrough'
import { STEP0_ABSTRACTION } from './step0/abstraction'
import { STEP0_SOURCES } from './step0/source'
import Step0Narration from './step0/narration.mdx'
import Step0Snippets from './step0/abstraction.mdx'
import step1Overview from './step1/1-overview.mdx'
import step1Matrix from './step1/2-matrix.mdx'
import step1Math from './step1/3-math.mdx'
import step1Layer from './step1/4-layer.mdx'
import step1Mlp from './step1/5-mlp.mdx'
import step1Main from './step1/6-main.mdx'

export const MODEL_CONTENT: Record<string, ModelContent> = {
  // The chapter slugs are the ones step0's four .mdx pages used, so every existing
  // /training/step0/learn/:slug link still resolves. It now seeks to that chapter's
  // timestamp instead of loading a page.
  step0: {
    kind: 'walkthrough',
    name: 'Single Neuron (Logistic Regression)',
    chapters: step0Chapters,
    scenes: step0Scenes,
    Narration: Step0Narration,
    sources: STEP0_SOURCES,
    // The closing page: the same neuron as a Python one-liner, and every decision
    // that one-liner made without asking. `python` is a slug alongside the chapter
    // slugs, so it must stay distinct from all of them.
    epilogue: {
      slug: 'python',
      title: 'The same model in Python',
      abstraction: STEP0_ABSTRACTION,
      Snippets: Step0Snippets,
    },
  },
  // In dependency order (matrix before layer, because a layer is two matrices;
  // layer before MLP, because an MLP is a stack of layers). grad_check.hpp has
  // no page of its own: it also ships in the source and is covered in a paragraph
  // rather than a chapter — see the MLP page.
  step1: {
    kind: 'pages',
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
