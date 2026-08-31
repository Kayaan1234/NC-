// The checks every abstraction ladder has to pass, written once.
//
// Extracted when step1 got a ladder of its own. Everything step0's suite asserted
// turned out to be model-agnostic, which is the sign the extraction was overdue
// rather than speculative: the alternative was copying seventeen tests and letting
// the copy rot.
//
// What these catch:
//
//   CAN catch — a C++ anchor that stopped resolving. The bottom rung shows the real
//   source, so renaming a function fails here instead of silently blanking a cell.
//
//   CAN catch — the manifest and the snippet MDX drifting apart, in both directions.
//
//   CAN catch — a library version claim going stale, for the libraries this repo
//   actually pins. The page asserts specific defaults, and defaults move: sklearn
//   deprecated `penalty='l2'` in 1.8. If the lockfile moves off a pinned version this
//   fails and somebody has to go and re-read the primary source.
//
//   CANNOT catch — whether the asserted defaults are TRUE. Nothing here runs sklearn
//   or torch. The values are read from primary sources by hand, and `provenance`
//   records whose word each claim is on. For PyTorch, which this repo does not
//   install at all, that is the only guarantee there is.
//
// Named `checks.ts` rather than `*.test.ts` so vitest does not collect it as an
// empty suite of its own.

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { extractAnchor, linesIn } from '../walkthrough/anchors'
import type { SourceBundle } from '../walkthrough/types'
import type { Abstraction } from './types'

const lockfile = readFileSync(
  new URL('../../../../backend/requirements-worker.lock.txt', import.meta.url),
  'utf8',
)

export function describeAbstraction(
  label: string,
  ladder: Abstraction,
  sources: SourceBundle,
  /** The model's abstraction.mdx, read off disk as TEXT. */
  snippetSource: string,
): void {
  const { rungs, concepts } = ladder
  const cells = concepts.flatMap((c) => c.cells.map((cell) => ({ concept: c.slug, cell })))

  describe(`${label}: shape`, () => {
    it('gives every concept a cell for every rung', () => {
      // A missing cell renders as a gap in the ladder, which reads as a layout bug
      // rather than as missing content.
      for (const concept of concepts) {
        expect(concept.cells.map((c) => c.rung).toSorted()).toEqual(
          rungs.map((r) => r.id).toSorted(),
        )
      }
    })

    it('names no unknown rung', () => {
      const known = new Set(rungs.map((r) => r.id))
      for (const { cell } of cells) expect(known.has(cell.rung)).toBe(true)
    })

    it('keeps concept slugs unique', () => {
      expect(new Set(concepts.map((c) => c.slug)).size).toBe(concepts.length)
    })

    it('puts the most abstract rung first and our own code last', () => {
      // The order IS the ladder, top to bottom, so it is load-bearing rather than
      // cosmetic. The page's argument only works read downwards.
      expect(rungs[0].id).toBe('sklearn')
      expect(rungs.at(-1)!.id).toBe('cpp')
      expect(rungs.at(-1)!.provenance.kind).toBe('ours')
    })
  })

  /**
   * The C++ cell of a concept, or a clear failure.
   *
   * The shape test above already guarantees this exists, but these run
   * independently: if a concept were missing its cpp cell, a bare `!` would surface
   * as "cannot read defaults of undefined" three assertions later, naming neither
   * the concept nor the real problem.
   */
  const cppCell = (concept: (typeof concepts)[number]) => {
    const cell = concept.cells.find((c) => c.rung === 'cpp')
    expect(cell, `concept ${concept.slug} has no cpp cell`).toBeDefined()
    return cell!
  }

  describe(`${label}: the thesis`, () => {
    it('leaves the C++ rung with nothing hidden, in every concept', () => {
      // This is the whole point of the page, so assert it rather than trusting an
      // author to keep it true. If our own code ever grows a "default", something has
      // gone wrong with either the code or the claim.
      for (const concept of concepts) expect(cppCell(concept).defaults).toEqual([])
    })

    it('shows the C++ rung as real source, never as an authored snippet', () => {
      for (const concept of concepts) expect(cppCell(concept).code.kind).toBe('source')
    })

    it('hides fewer decisions the further down the ladder you go', () => {
      // The gradient is the argument. It does not have to be strictly decreasing at
      // every step, but it must not increase: a rung lower down that hid MORE than the
      // one above it would mean the page is telling a story its own data contradicts.
      const counts = rungs.map((r) =>
        concepts.reduce(
          (n, c) => n + (c.cells.find((cell) => cell.rung === r.id)?.defaults.length ?? 0),
          0,
        ),
      )
      for (let i = 1; i < counts.length; i++) {
        expect(counts[i]).toBeLessThanOrEqual(counts[i - 1])
      }
      // And the top rung must actually hide something, or there is no page here.
      expect(counts[0]).toBeGreaterThan(0)
    })
  })

  describe(`${label}: C++ references resolve against the real source`, () => {
    const refs = cells.flatMap(({ concept, cell }) =>
      cell.code.kind === 'source'
        ? cell.code.refs.map((ref) => [`${concept}/${cell.rung}`, ref] as const)
        : [],
    )

    it('references some code at all', () => {
      expect(refs.length).toBeGreaterThan(0)
    })

    it.each(refs)('%s resolves to a readable slice', (_id, ref) => {
      if (ref.kind !== 'source') return
      const src = sources.raw[ref.file]
      expect(src, `no source file named ${ref.file}`).toBeDefined()
      const lines = linesIn(src, extractAnchor(src, ref.anchor))
      expect(lines.length).toBeGreaterThan(1)
      // A cell taller than this stops being comparable with the three above it. If a
      // function outgrows it, the concept wants splitting rather than the cap raising.
      expect(lines.length).toBeLessThanOrEqual(30)
    })

    it.each(refs)('%s emphasises lines that exist in its own slice', (_id, ref) => {
      if (ref.kind !== 'source' || !ref.emphasise?.length) return
      const src = sources.raw[ref.file]
      const lines = linesIn(src, extractAnchor(src, ref.anchor))
      for (const needle of ref.emphasise) {
        expect(lines.some((l) => l.includes(needle)), `no line contains ${needle}`).toBe(true)
      }
    })
  })

  describe(`${label}: authored snippets and the MDX agree`, () => {
    const wanted = cells
      .flatMap(({ cell }) => (cell.code.kind === 'authored' ? [cell.code.snippet] : []))
      .toSorted()

    const present = [...snippetSource.matchAll(/<Snippet\s+id="([^"]+)"/g)]
      .map((m) => m[1])
      .toSorted()

    it('has a snippet for every authored cell, and a cell for every snippet', () => {
      // Sorted arrays rather than sets so a failure prints the difference.
      expect(present).toEqual(wanted)
    })

    it('uses each snippet id once', () => {
      expect(new Set(present).size).toBe(present.length)
    })

    it('tags every opening fence with a language so shiki highlights it', () => {
      // vite.config.ts sets fallbackLanguage 'text', so an untagged or misspelled
      // fence degrades silently to plain text instead of failing the build. The
      // content README calls that out as a silent authoring trap, which is exactly
      // the kind worth a test.
      //
      // Fences alternate open/close down the file, and a closing fence is bare, so
      // the even ones carry the language and the odd ones must not.
      const fences = [...snippetSource.matchAll(/^```(\w*)$/gm)].map((m) => m[1])

      expect(fences.length).toBeGreaterThan(0)
      expect(fences.length % 2).toBe(0) // balanced
      expect(fences.length / 2).toBe(present.length) // one block per snippet

      fences.forEach((lang, i) => {
        expect(lang).toBe(i % 2 === 0 ? 'python' : '')
      })
    })
  })

  describe(`${label}: version claims`, () => {
    const locked = rungs.flatMap((r) => (r.provenance.kind === 'locked' ? [r.provenance] : []))

    it('pins at least one claim to something this repo installs', () => {
      expect(locked.length).toBeGreaterThan(0)
    })

    it.each(locked.map((p) => [p.pkg, p.version] as const))(
      '%s %s still matches the worker lockfile',
      (pkg, version) => {
        // The defaults on this page were read against these exact versions. When the
        // lockfile moves, somebody has to go back to the primary source, because
        // library defaults do change: sklearn deprecated penalty='l2' in 1.8.
        expect(lockfile).toContain(`${pkg}==${version}`)
      },
    )

    it('gives every cited claim a date it was read', () => {
      // A claim about a library this repo does not install has no automated backstop,
      // so the least it can carry is when a human last checked it.
      for (const rung of rungs) {
        if (rung.provenance.kind === 'cited') {
          expect(rung.provenance.checked).toMatch(/^\d{4}-\d{2}-\d{2}$/)
          expect(rung.provenance.url).toMatch(/^https:\/\//)
        }
      }
    })
  })

  describe(`${label}: the defaults themselves`, () => {
    it('gives every default a note that says something', () => {
      for (const { cell } of cells) {
        for (const d of cell.defaults) expect(d.note.trim().length).toBeGreaterThan(20)
      }
    })

    it('keeps any one cell readable', () => {
      // BridgeVerdict.tsx's rule, applied here: a page that opens with every parameter
      // of the sklearn API teaches a reader about the sklearn API. If a cell needs
      // more than this, the concept wants splitting.
      for (const { cell } of cells) expect(cell.defaults.length).toBeLessThanOrEqual(5)
    })

    it('claims at least one default MATCHES our code', () => {
      // Tone, enforced. torch.optim.SGD's momentum=0 really is the update rule from
      // update(). Without any matches the page would be an argument against using
      // libraries, which is not the argument it is making.
      const verdicts = cells.flatMap(({ cell }) => cell.defaults.map((d) => d.verdict))
      expect(verdicts).toContain('matches')
      expect(verdicts).toContain('differs')
    })

    it('keeps em-dashes out of anything a reader sees', () => {
      // The voice rules in content/README.md govern every visible word, and these
      // notes are prose that happens to live in a .ts file.
      for (const { cell } of cells) {
        for (const d of cell.defaults) expect(d.note).not.toContain('—')
      }
      for (const rung of rungs) expect(rung.blurb).not.toContain('—')
      for (const c of concepts) expect(c.question).not.toContain('—')
    })
  })
}
