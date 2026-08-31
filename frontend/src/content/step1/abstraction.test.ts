// step1's abstraction ladder, checked against the things it makes claims about.
//
// The shared assertions are in ../abstraction/checks.ts. What is here is what is
// true of step1's ladder and not of ladders in general.
//
// The sklearn claims on this page are in better shape than most: they were read on
// 2026-08-30 out of the INSTALLED scikit-learn 1.9.0, which is the version the worker
// lockfile pins, so the shared version check is guarding a claim somebody actually
// executed rather than one they read on a docs page for a different release.

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { STEP1_ABSTRACTION } from './abstraction'
import { STEP1_SOURCES } from './source'
import { describeAbstraction } from '../abstraction/checks'
import { SCENES } from './walkthrough'

describeAbstraction(
  'step1',
  STEP1_ABSTRACTION,
  STEP1_SOURCES,
  readFileSync(new URL('./abstraction.mdx', import.meta.url), 'utf8'),
)

describe('step1 in particular', () => {
  const { concepts } = STEP1_ABSTRACTION

  it('keeps the absorbed softmax as a MATCH on the PyTorch rung', () => {
    // The single most valuable claim on the page, and the one an edit is most likely
    // to weaken by accident. nn.CrossEntropyLoss taking logits and applying
    // log_softmax itself is the same trick as softmax_cross_entropy_loss_grad, and it
    // is why MLP.hpp insists the last layer be LINEAR. Downgrading it to 'differs'
    // would break the through-line from the walkthrough's longest beat to this page.
    const loss = concepts.find((c) => c.slug === 'loss')!
    const torch = loss.cells.find((c) => c.rung === 'pytorch')!
    const logits = torch.defaults.find((d) => d.name === 'expects logits')

    expect(logits, 'the expects-logits default was renamed or removed').toBeDefined()
    expect(logits!.verdict).toBe('matches')
    expect(logits!.note).toContain('LINEAR')
  })

  it('covers the backward pass, which step0 had no cell for', () => {
    // step0's ladder had no backward concept, because one neuron's gradient is two
    // lines. At this size the backward pass is most of the interesting code, and it
    // is where PyTorch's accumulate-by-default behaviour differs from ours.
    expect(concepts.map((c) => c.slug)).toContain('backward')
  })

  it('draws its C++ from more than one file in most concepts', () => {
    // The reason RungCode.source takes an ARRAY. step1's answer to "how does it go
    // forwards" lives in MLP.hpp AND layer.hpp, and a ladder that showed only one of
    // them would be quietly answering a different question.
    const spans = concepts.filter((c) => {
      const cpp = c.cells.find((cell) => cell.rung === 'cpp')!
      return cpp.code.kind === 'source' && new Set(
        cpp.code.refs.flatMap((r) => (r.kind === 'source' ? [r.file] : [])),
      ).size > 1
    })
    expect(spans.length).toBeGreaterThanOrEqual(3)
  })

  it('points at code the walkthrough also anchors', () => {
    // The epilogue is the closing page of the same flow, so the C++ it shows should
    // be code the reader has already been walked through. A ladder anchored entirely
    // on functions the walkthrough skipped would be introducing new material at the
    // end rather than recasting what came before.
    const walked = new Set(
      SCENES.flatMap((s) => (s.code?.kind === 'source' ? [`${s.code.file}:${s.code.anchor}`] : [])),
    )
    const ladder = concepts.flatMap((c) => {
      const cpp = c.cells.find((cell) => cell.rung === 'cpp')!
      return cpp.code.kind === 'source'
        ? cpp.code.refs.flatMap((r) => (r.kind === 'source' ? [`${r.file}:${r.anchor}`] : []))
        : []
    })

    const shared = ladder.filter((a) => walked.has(a))
    expect(shared.length / ladder.length).toBeGreaterThanOrEqual(0.5)
  })
})
