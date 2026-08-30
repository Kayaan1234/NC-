// The checks every walkthrough has to pass, written once.
//
// Extracted when step1 became the second walkthrough, which is the moment to do it:
// the alternative is copying step0's suite and letting the two drift, and a test
// suite that has drifted is worse than one that never existed, because it still
// reports green.
//
// What these catch:
//
//   CAN catch — the manifest and the prose drifting apart. Scene ids and <Beat> ids
//   are matched by hand across two files, so a rename in one is the single most
//   likely authoring mistake. In the player the symptom is a caption that silently
//   renders nothing, which looks like a CSS problem and can survive a review; in the
//   text view the symptom is a beat that never appears at all.
//
//   CAN catch — an anchor that no longer resolves. Every code reference is exercised
//   against the real C++, so editing or renaming a function fails the suite instead
//   of blanking a code panel in production.
//
//   CANNOT catch — whether the timings feel right, or whether the words are any
//   good. Those come from watching it.
//
// This file is named `checks.ts` rather than `*.test.ts` on purpose: vitest collects
// the latter, and a helper that declares no tests of its own would be reported as an
// empty suite.

import { describe, expect, it } from 'vitest'

import { extractAnchor, linesIn } from './anchors'
import { chapterStart, totalDuration } from './timeline'
import type { Chapter, Scene, StageState } from './types'

export interface WalkthroughUnderTest {
  chapters: readonly Chapter[]
  scenes: readonly Scene<StageState>[]
  /** The narration MDX, read off disk as TEXT. */
  narration: string
  /** Raw source text, keyed by file, as the model's source.ts exports it. */
  source: Readonly<Record<string, string>>
  /** Highlighted HTML, one entry per line, keyed the same way. */
  highlighted: Readonly<Record<string, string[]>>
  /**
   * The slugs that must keep resolving, in rail order. Spelled out by the caller
   * rather than derived from `chapters`, because the point is to pin them against
   * what the model's old .mdx pages used: deriving them from the thing under test
   * would assert nothing.
   */
  slugs: string[]
  /** Acceptable total runtime, in minutes. */
  runtime: { min: number; max: number }
}

/**
 * The narration is read off disk rather than imported. Importing would compile the
 * MDX to a component, and counting beats would then mean rendering React, which
 * these suites have no DOM for. The ids are a property of the text.
 */
export function beatIds(narration: string): string[] {
  return [...narration.matchAll(/<Beat\s+id="([^"]+)"/g)].map((m) => m[1])
}

export function describeWalkthrough(label: string, w: WalkthroughUnderTest): void {
  const { chapters, scenes, source, highlighted } = w

  describe(`${label}: scenes and narration beats`, () => {
    const ids = beatIds(w.narration)

    it('has a beat for every scene, and a scene for every beat', () => {
      // Compared as sorted arrays rather than sets so a failure prints the diff.
      // toSorted, so neither the beat order nor the scene order is disturbed for the
      // assertions below that depend on it.
      expect(ids.toSorted()).toEqual(scenes.map((s) => s.id).toSorted())
    })

    it('orders the beats the way the scenes play', () => {
      // Not required by the player, which looks beats up by id, but the text view
      // renders them in document order, so a mismatch would read out of sequence.
      expect(ids).toEqual(scenes.map((s) => s.id))
    })

    it('uses each scene id exactly once', () => {
      expect(new Set(scenes.map((s) => s.id)).size).toBe(scenes.length)
    })
  })

  describe(`${label}: chapters`, () => {
    it('gives every chapter at least one scene', () => {
      // chapterStart throws otherwise, which would break the rail rather than the
      // build; this turns it into a test failure.
      for (const chapter of chapters) {
        expect(() => chapterStart(scenes, chapter.slug)).not.toThrow()
      }
    })

    it('keeps every scene in a declared chapter', () => {
      const slugs = new Set(chapters.map((c) => c.slug))
      for (const scene of scenes) expect(slugs.has(scene.chapter)).toBe(true)
    })

    it('keeps each chapter contiguous and in rail order', () => {
      // The rail seeks to a chapter's first scene, so a chapter appearing in two
      // separate runs would make the second run unreachable from the rail.
      const order = scenes.map((s) => s.chapter)
      const firstAppearance = [...new Set(order)]
      expect(firstAppearance).toEqual(chapters.map((c) => c.slug))

      for (const slug of firstAppearance) {
        const indices = order.flatMap((c, i) => (c === slug ? [i] : []))
        expect(indices.at(-1)! - indices[0]).toBe(indices.length - 1)
      }
    })

    it('preserves the slugs the old MDX pages used', () => {
      // Existing /training/<model>/learn/:slug links must keep resolving. They now
      // seek to a timestamp, but a changed slug would 404 an old bookmark.
      expect(chapters.map((c) => c.slug)).toEqual(w.slugs)
    })
  })

  describe(`${label}: durations`, () => {
    it(`runs for roughly ${w.runtime.min} to ${w.runtime.max} minutes`, () => {
      // A fat-fingered `seconds: 600` should fail loudly rather than produce a
      // walkthrough nobody sits through.
      const total = totalDuration(scenes)
      expect(total).toBeGreaterThan(w.runtime.min * 60)
      expect(total).toBeLessThan(w.runtime.max * 60)
    })

    it('gives every scene a sane, positive length', () => {
      for (const scene of scenes) {
        expect(scene.seconds).toBeGreaterThan(0)
        expect(scene.seconds).toBeLessThanOrEqual(60)
      }
    })
  })

  describe(`${label}: code references resolve against the real source`, () => {
    const sourceRefs = scenes.flatMap((s) =>
      s.code?.kind === 'source' ? [{ id: s.id, ref: s.code }] : [],
    )

    it('references some code at all', () => {
      expect(sourceRefs.length).toBeGreaterThan(0)
    })

    it.each(sourceRefs.map((r) => [r.id, r.ref] as const))(
      '%s resolves to a non-empty slice',
      (_id, ref) => {
        const src = source[ref.file]
        expect(src, `no source file named ${ref.file}`).toBeDefined()
        const lines = linesIn(src, extractAnchor(src, ref.anchor))

        expect(lines.length).toBeGreaterThan(1)
        // A panel taller than this is not readable beside a caption; if a function
        // grows past it, the scene needs splitting rather than the limit raising.
        // This is also what stops anyone anchoring a whole struct: at step1 sizes,
        // `struct Layer` is 77 lines and would fill the screen with declarations.
        expect(lines.length).toBeLessThanOrEqual(30)
      },
    )

    it.each(
      sourceRefs.flatMap((r) => (r.ref.emphasise?.length ? [[r.id, r.ref] as const] : [])),
    )('%s emphasises lines that actually exist in its slice', (_id, ref) => {
      const src = source[ref.file]
      const lines = linesIn(src, extractAnchor(src, ref.anchor))
      // An emphasise needle matching nothing dims the whole block for no reason,
      // which reads as a rendering bug rather than an authoring one.
      for (const needle of ref.emphasise!) {
        expect(lines.some((l) => l.includes(needle)), `no line contains ${needle}`).toBe(true)
      }
    })

    it('labels every aside so it cannot be taken for the shipped source', () => {
      // The whole point of the aside kind: these snippets are deliberately not in
      // the C++, and a reader must never be left thinking they are.
      for (const scene of scenes) {
        if (scene.code?.kind === 'aside') {
          expect(scene.code.note.trim().length).toBeGreaterThan(0)
        }
      }
    })
  })

  describe(`${label}: the build-time highlighter`, () => {
    // The panel computes a line range from the RAW text and then indexes the
    // HIGHLIGHTED array with it. If the two disagree on how many lines the file has,
    // every slice is silently off by the difference, which shows the wrong code
    // without erroring. Shiki drops a trailing empty line that split('\n') keeps,
    // which is exactly how the two would come apart.
    it.each(Object.keys(source))('%s has one highlighted line per raw line', (file) => {
      expect(highlighted[file]).toHaveLength(source[file].split('\n').length)
    })

    it('actually emits markup rather than plain text', () => {
      const joined = Object.values(highlighted)[0].join('')
      expect(joined).toContain('<span style="color:')
    })

    it('escapes the angle brackets C++ is full of', () => {
      // std::vector<double> would otherwise open a tag and eat the rest of the line.
      const joined = Object.values(highlighted).flat().join('')
      expect(joined).toContain('&lt;')
      expect(joined).not.toContain('<double>')
    })
  })
}
