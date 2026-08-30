// Registry of authored "learn" content, keyed by backend model_id (the same id the
// menu links to and the training page reads from the URL). A model with no entry
// here simply has no learn flow: its menu card links straight to training.
//
// Two shapes are supported — see types.ts — and both models are currently the same
// one: a narrated walkthrough, one timeline with chapters that seek. The paged .mdx
// shape is still live and is what a new model should start as; step0 and step1 were
// both written that way first. Adding either is one entry here plus its content
// files — see content/README.md.

import { walkthrough, type ModelContent } from './types'
import { CHAPTERS as step0Chapters, SCENES as step0Scenes } from './step0/walkthrough'
import { STEP0_ABSTRACTION } from './step0/abstraction'
import { STEP0_SOURCES } from './step0/source'
import Step0Stage from '../components/walkthrough/Step0Stage'
import Step0Narration from './step0/narration.mdx'
import Step0Snippets from './step0/abstraction.mdx'
import { CHAPTERS as step1Chapters, SCENES as step1Scenes } from './step1/walkthrough'
import { STEP1_SOURCES } from './step1/source'
import Step1Stage from '../components/walkthrough/Step1Stage'
import Step1Narration from './step1/narration.mdx'

export const MODEL_CONTENT: Record<string, ModelContent> = {
  // The chapter slugs are the ones step0's four .mdx pages used, so every existing
  // /training/step0/learn/:slug link still resolves. It now seeks to that chapter's
  // timestamp instead of loading a page.
  step0: walkthrough({
    name: 'Single Neuron (Logistic Regression)',
    chapters: step0Chapters,
    scenes: step0Scenes,
    Stage: Step0Stage,
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
  }),
  // Chapters in dependency order (matrix before layer, because a layer is two
  // matrices; layer before MLP, because an MLP is a stack of layers), and the slugs
  // are the ones step1's six .mdx pages used, so old links still resolve.
  //
  // grad_check.hpp has no chapter of its own. It ships in the source and gets one
  // beat in the MLP chapter, which is the right weight for it.
  step1: walkthrough({
    name: 'Multilayer Perceptron',
    chapters: step1Chapters,
    scenes: step1Scenes,
    Stage: Step1Stage,
    Narration: Step1Narration,
    sources: STEP1_SOURCES,
  }),
}

export function getModelContent(id: string | undefined): ModelContent | undefined {
  return id ? MODEL_CONTENT[id] : undefined
}

export function hasContent(id: string): boolean {
  return id in MODEL_CONTENT
}
