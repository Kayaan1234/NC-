import type { ReactNode } from 'react'

// A numbered frame for the learn pages: the diagram on black, the caption beneath
// it on the page.
//
// This was a textbook plate — line art on the page background, no card and no
// tint. It became a frame when the site took its visual language from 3Blue1Brown
// rather than from a printed maths text. The caption deliberately stays OUTSIDE
// the frame, in chrome colours: it is the page talking about the figure, not part
// of what the figure shows.
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
      <div className="figure__frame figure-surface">{children}</div>
      <figcaption>
        <b>Figure {n}</b> — {caption}
      </figcaption>
    </figure>
  )
}
