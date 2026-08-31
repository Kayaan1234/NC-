// The step0 walkthrough manifest, checked against the narration it is keyed to.
//
// Almost all of this lives in ../walkthrough/checks.ts now, shared with step1. Read
// that file for what these assertions catch and, just as importantly, what they do
// not: they check the manifest is consistent, never that the walkthrough is good.
//
// What stays here is only what is true of step0 and not of walkthroughs in general.

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { CHAPTERS, SCENES } from './walkthrough'
import { STEP0_HIGHLIGHTED, STEP0_SOURCE } from './source'
import { describeWalkthrough } from '../walkthrough/checks'

describeWalkthrough('step0', {
  chapters: CHAPTERS,
  scenes: SCENES,
  narration: readFileSync(new URL('./narration.mdx', import.meta.url), 'utf8'),
  source: STEP0_SOURCE,
  highlighted: STEP0_HIGHLIGHTED,
  // The four slugs step0's .mdx pages used, before it became a walkthrough.
  slugs: ['overview', 'math', 'logistic_regression', 'main'],
  runtime: { min: 6, max: 15 },
})

describe('step0 in particular', () => {
  it('builds the neuron one part at a time before showing any code', () => {
    // The overview chapter is the reason the walkthrough format was chosen over
    // pages: a reader should be able to draw the object before being shown a struct.
    // A code panel appearing in it would mean that argument had been abandoned.
    const overview = SCENES.filter((s) => s.chapter === 'overview')
    expect(overview.every((s) => s.code === undefined)).toBe(true)
    expect(overview.map((s) => (s.stage.kind === 'neuron' ? s.stage.reveal : null))).toEqual([
      'inputs',
      'weights',
      'sum',
      'bias',
      'sigmoid',
      'all',
      'all',
    ])
  })
})
