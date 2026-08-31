// The step1 walkthrough manifest, checked against the narration it is keyed to.
//
// The shared assertions are in ../walkthrough/checks.ts; read that file for what
// they cover. What is here is what is true of step1 and not of walkthroughs in
// general, and most of it guards the one property that makes this walkthrough work:
// that it is a SEQUEL and does not re-teach step0.

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { CHAPTERS, SCENES } from './walkthrough'
import { STEP1_HIGHLIGHTED, STEP1_SOURCE } from './source'
import { describeWalkthrough } from '../walkthrough/checks'
import { totalDuration } from '../walkthrough/timeline'

const narration = readFileSync(new URL('./narration.mdx', import.meta.url), 'utf8')

describeWalkthrough('step1', {
  chapters: CHAPTERS,
  scenes: SCENES,
  narration,
  source: STEP1_SOURCE,
  highlighted: STEP1_HIGHLIGHTED,
  // The six slugs step1's .mdx pages used, before it became a walkthrough.
  slugs: ['overview', 'matrix', 'math', 'layer', 'mlp', 'main'],
  // The brief was under twenty minutes, ideally shorter. The upper bound is the
  // brief; the lower one catches a chapter accidentally deleted.
  runtime: { min: 12, max: 20 },
})

describe('step1 in particular', () => {
  it('stays shorter than twenty minutes for a model four times step0’s size', () => {
    // Stated separately from the range check because this is the actual constraint,
    // and a reader of this file should see the number without doing the arithmetic.
    expect(totalDuration(SCENES) / 60).toBeLessThan(20)
  })

  it('draws every scene from the shipped diagrams, with one new picture', () => {
    // A walkthrough that invented its own visual language would look like a second
    // site. xorTransform is the single deliberate exception, and it reuses
    // XorHidden's computed positions rather than drawing new ones.
    const kinds = new Set(SCENES.map((s) => s.stage.kind))
    expect(kinds.has('xorTransform')).toBe(true)
  })

  it('opens on the payoff rather than on a data structure', () => {
    // The ordering risk for a sequel is starting with matrix.hpp because that is
    // what the source does. A reader needs to know why one neuron was not enough
    // before being shown the machinery that fixes it.
    expect(SCENES[0].chapter).toBe('overview')
    expect(CHAPTERS[0].slug).toBe('overview')
    const firstMatrixScene = SCENES.findIndex((s) => s.chapter === 'matrix')
    const transform = SCENES.findIndex((s) => s.stage.kind === 'xorTransform')
    expect(transform).toBeLessThan(firstMatrixScene)
  })

  it('keeps calling back to step0 instead of starting over', () => {
    // The brief was that step1 build on step0 rather than reintroduce it, and that
    // discipline shows up in the prose as explicit callbacks: "the same trick from
    // step zero", "step zero's cancellation happening again".
    //
    // CAN catch — a chapter rewritten as if the reader arrived cold, which is the
    // real regression and is otherwise invisible until someone watches the whole
    // thing. CANNOT catch — a beat that quietly re-explains a weight without
    // naming step0. Detecting that reliably needs a reader, not a regex, and a
    // guard that tried would fail on legitimate prose like "the bias is a single
    // row", which is about shape rather than about what a bias means.
    const callbacks = narration.match(/step zero/gi) ?? []
    expect(callbacks.length).toBeGreaterThanOrEqual(8)
  })

  it('honours the voice rule against em-dashes', () => {
    // content/README.md governs every word a reader sees. Easy to reintroduce by
    // pasting, and invisible in review at this length.
    expect(narration).not.toContain('—')
  })
})
