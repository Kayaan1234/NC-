import { useMemo } from 'react'

import { extractAnchor, emphasisedLines } from '../../content/walkthrough/anchors'
import type { CodeRef, SourceBundle } from '../../content/walkthrough/types'

// The code beside the narration.
//
// Two kinds of block, and the difference is not cosmetic. A `source` block is a
// slice of the real file that compiles and trains, located by function signature and
// highlighted at build time. An `aside` is something written for the explanation
// that is deliberately absent from the project, and it carries a visible label
// saying so. A reader who cannot tell those apart would come away believing the
// codebase contains code it does not, which is the failure the old MDX pages were
// one careless edit away from: they quoted C++ by hand, and one excerpt had already
// drifted from the file it claimed to show.
//
// The <pre> is kept mounted across scenes and only its contents change. Remounting
// it would reset the scroll position of a block the reader may have scrolled, and
// would make the panel flash on every beat.

/**
 * One anchored slice of a model's real source, highlighted.
 *
 * Exported because the abstraction page renders several of these in a row for its
 * C++ rung. Slicing lives here rather than being reimplemented there, so both
 * surfaces get the same anchor semantics and the same anti-drift guarantee.
 */
export function SourceBlock({
  sources,
  file,
  anchor,
  emphasise,
}: {
  sources: SourceBundle
  file: string
  anchor: string
  emphasise?: string[]
}) {
  const { html, marked } = useMemo(() => {
    const raw = sources.raw[file]
    if (raw === undefined) throw new Error(`SourceBlock: no source file named ${JSON.stringify(file)}`)
    const range = extractAnchor(raw, anchor)
    const slice = sources.highlighted[file].slice(range.start, range.end + 1)
    const rawSlice = raw.split('\n').slice(range.start, range.end + 1)
    return { html: slice, marked: emphasisedLines(rawSlice, emphasise) }
  }, [sources, file, anchor, emphasise])

  // No emphasis means every line reads at full strength. Dimming everything when a
  // scene simply has nothing to single out would make the default state the quiet
  // one, which is backwards.
  const dimOthers = marked.size > 0

  return (
    <>
      <div className="codepanel__name">{file}</div>
      <pre className="codepanel__code">
        <code>
          {html.map((line, i) => (
            <span
              key={i}
              className={
                dimOthers && !marked.has(i) ? 'codepanel__line codepanel__line--dim' : 'codepanel__line'
              }
              // Build-time output from vite-plugin-cpp-highlight, never user input.
              dangerouslySetInnerHTML={{ __html: line || ' ' }}
            />
          ))}
        </code>
      </pre>
    </>
  )
}

function AsideBlock({ code, note }: { code: string; note: string }) {
  return (
    <>
      <div className="codepanel__name codepanel__name--aside">{note}</div>
      <pre className="codepanel__code codepanel__code--aside">
        <code>{code}</code>
      </pre>
    </>
  )
}

export default function CodePanel({
  code,
  sources,
}: {
  code?: CodeRef
  sources: SourceBundle
}) {
  // The panel holds its height when a scene has no code, so the caption above it
  // does not jump up and down between beats.
  if (!code) return <div className="codepanel codepanel--empty" aria-hidden="true" />

  return (
    <div className="codepanel">
      {code.kind === 'source' ? (
        <SourceBlock
          sources={sources}
          file={code.file}
          anchor={code.anchor}
          emphasise={code.emphasise}
        />
      ) : (
        <AsideBlock code={code.code} note={code.note} />
      )}
    </div>
  )
}
