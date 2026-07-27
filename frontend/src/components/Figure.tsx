import type { ReactNode } from 'react'

// A numbered plate for the learn pages, in the register of a maths textbook: line
// art on the page background with a caption beneath it, no card, no tint, no frame.
//
// The number is an explicit prop rather than something a context provider counts.
// A counter would renumber every figure the moment a section was reordered in
// content/index.ts, and MDX pages are separate modules that don't share a render
// pass — so the count would depend on which page you happened to load first.

export default function Figure({
  n,
  caption,
  children,
}: {
  n: number
  caption: string
  children: ReactNode
}) {
  return (
    <figure className="figure">
      {children}
      <figcaption>
        <b>Figure {n}</b> — {caption}
      </figcaption>
    </figure>
  )
}
