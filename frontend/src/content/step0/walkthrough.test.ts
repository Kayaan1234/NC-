// The step0 walkthrough manifest, checked against the narration it is keyed to.
//
// What these tests catch:
//
//   CAN catch — the manifest and the prose drifting apart. Scene ids and <Beat> ids
//   are matched by hand across two files, so a rename in one is the single most
//   likely authoring mistake here. In the player the symptom is a caption that
//   silently renders nothing, which looks like a CSS problem and can survive a
//   review; in the text view the symptom is a beat that never appears at all.
//
//   CAN catch — an anchor that no longer resolves. Every code reference is
//   exercised against the real Step0 source below, so editing or renaming a C++
//   function fails the suite instead of blanking a code panel in production.
//
//   CANNOT catch — whether the timings feel right, or whether the words are any
//   good. Those come from watching it.
//
// The narration is read off disk rather than imported. Importing would compile the
// MDX to a component, and counting beats would then mean rendering React, which
// this suite has no DOM for. The ids are a property of the text.

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { CHAPTERS, SCENES } from './walkthrough'
import { STEP0_HIGHLIGHTED, STEP0_SOURCE } from './source'
import { extractAnchor, linesIn } from '../walkthrough/anchors'
import { chapterStart, totalDuration } from '../walkthrough/timeline'

const narration = readFileSync(new URL('./narration.mdx', import.meta.url), 'utf8')

function beatIds(source: string): string[] {
  return [...source.matchAll(/<Beat\s+id="([^"]+)"/g)].map((m) => m[1])
}

describe('scenes and narration beats', () => {
  const ids = beatIds(narration)

  it('has a beat for every scene, and a scene for every beat', () => {
    // Compared as sorted arrays rather than sets so a failure prints the diff.
    expect([...ids].sort()).toEqual(SCENES.map((s) => s.id).sort())
  })

  it('orders the beats the way the scenes play', () => {
    // Not required by the player, which looks beats up by id, but the text view
    // renders them in document order, so a mismatch would read out of sequence.
    expect(ids).toEqual(SCENES.map((s) => s.id))
  })

  it('uses each scene id exactly once', () => {
    expect(new Set(SCENES.map((s) => s.id)).size).toBe(SCENES.length)
  })
})

describe('chapters', () => {
  it('gives every chapter at least one scene', () => {
    // chapterStart throws otherwise, which would break the rail rather than the
    // build; this turns it into a test failure.
    for (const chapter of CHAPTERS) {
      expect(() => chapterStart(SCENES, chapter.slug)).not.toThrow()
    }
  })

  it('keeps every scene in a declared chapter', () => {
    const slugs = new Set(CHAPTERS.map((c) => c.slug))
    for (const scene of SCENES) expect(slugs.has(scene.chapter)).toBe(true)
  })

  it('keeps each chapter contiguous and in rail order', () => {
    // The rail seeks to a chapter's first scene, so a chapter appearing in two
    // separate runs would make the second run unreachable from the rail.
    const order = SCENES.map((s) => s.chapter)
    const firstAppearance = [...new Set(order)]
    expect(firstAppearance).toEqual(CHAPTERS.map((c) => c.slug))

    for (const slug of firstAppearance) {
      const indices = order.flatMap((c, i) => (c === slug ? [i] : []))
      expect(indices.at(-1)! - indices[0]).toBe(indices.length - 1)
    }
  })

  it('preserves the slugs the old MDX pages used', () => {
    // Existing /training/step0/learn/:slug links must keep resolving. They now
    // seek to a timestamp, but a changed slug would 404 an old bookmark.
    expect(CHAPTERS.map((c) => c.slug)).toEqual([
      'overview',
      'math',
      'logistic_regression',
      'main',
    ])
  })
})

describe('durations', () => {
  it('runs for roughly ten minutes', () => {
    // A fat-fingered `seconds: 600` should fail loudly rather than produce a
    // walkthrough nobody sits through.
    const total = totalDuration(SCENES)
    expect(total).toBeGreaterThan(6 * 60)
    expect(total).toBeLessThan(15 * 60)
  })

  it('gives every scene a sane, positive length', () => {
    for (const scene of SCENES) {
      expect(scene.seconds).toBeGreaterThan(0)
      expect(scene.seconds).toBeLessThanOrEqual(60)
    }
  })
})

describe('code references resolve against the real source', () => {
  const sourceRefs = SCENES.flatMap((s) =>
    s.code?.kind === 'source' ? [{ id: s.id, ref: s.code }] : [],
  )

  it('references some code at all', () => {
    expect(sourceRefs.length).toBeGreaterThan(0)
  })

  it.each(sourceRefs.map((r) => [r.id, r.ref] as const))(
    '%s resolves to a non-empty slice',
    (_id, ref) => {
      const src = STEP0_SOURCE[ref.file]
      const range = extractAnchor(src, ref.anchor)
      const lines = linesIn(src, range)

      expect(lines.length).toBeGreaterThan(1)
      // A panel taller than this is not readable beside a caption; if a function
      // grows past it, the scene needs splitting rather than the limit raising.
      expect(lines.length).toBeLessThanOrEqual(30)
    },
  )

  it.each(
    sourceRefs
      .filter((r) => r.ref.emphasise?.length)
      .map((r) => [r.id, r.ref] as const),
  )('%s emphasises lines that actually exist in its slice', (_id, ref) => {
    const src = STEP0_SOURCE[ref.file]
    const lines = linesIn(src, extractAnchor(src, ref.anchor))
    // An emphasise needle matching nothing dims the whole block for no reason,
    // which reads as a rendering bug rather than an authoring one.
    for (const needle of ref.emphasise!) {
      expect(lines.some((l) => l.includes(needle))).toBe(true)
    }
  })
})

describe('the build-time highlighter', () => {
  // The panel computes a line range from the RAW text and then indexes the
  // HIGHLIGHTED array with it. If the two disagree on how many lines the file has,
  // every slice is silently off by the difference, which shows the wrong code
  // without erroring. Shiki drops a trailing empty line that split('\n') keeps,
  // which is exactly how the two would come apart.
  it.each(Object.keys(STEP0_SOURCE) as (keyof typeof STEP0_SOURCE)[])(
    '%s has one highlighted line per raw line',
    (file) => {
      expect(STEP0_HIGHLIGHTED[file]).toHaveLength(STEP0_SOURCE[file].split('\n').length)
    },
  )

  it('actually emits markup rather than plain text', () => {
    const joined = STEP0_HIGHLIGHTED['math.hpp'].join('')
    expect(joined).toContain('<span style="color:')
  })

  it('escapes the angle brackets C++ is full of', () => {
    // std::vector<double> would otherwise open a tag and eat the rest of the line.
    const joined = STEP0_HIGHLIGHTED['logistic_regression.hpp'].join('')
    expect(joined).toContain('&lt;')
    expect(joined).not.toContain('<double>')
  })
})

describe('asides', () => {
  it('labels every aside so it cannot be taken for the shipped source', () => {
    // The whole point of the aside kind: these snippets are deliberately not in
    // the C++, and a reader must never be left thinking they are.
    for (const scene of SCENES) {
      if (scene.code?.kind === 'aside') {
        expect(scene.code.note.trim().length).toBeGreaterThan(0)
      }
    }
  })
})
