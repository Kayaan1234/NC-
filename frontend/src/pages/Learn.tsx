import { Link, Navigate, useParams } from 'react-router-dom'
import { getModelContent } from '../content'
import Walkthrough from '../components/walkthrough/Walkthrough'
import AbstractionPage from '../components/abstraction/AbstractionPage'

// The "read about the model" flow, reached from the /training menu for any model
// that has authored content (see content/index.ts). One route component serves the
// whole sequence: /training/:modelId/learn is the first section, and
// /training/:modelId/learn/:slug is a specific section. Pagination, prev/next, the
// table of contents and the position indicator are all derived from the model's
// `sections` array, so adding a page never touches this file.
//
// Deliberately gated on logged-in only (RequireAuth in App.tsx), NOT verified email:
// reading is what motivates verifying, and nothing here calls a /train endpoint. The
// "skip to training" links point at /training/:modelId, which enforces verification
// itself at the point of actually running a job.
//
// Layout is a two-column grid: a sticky rail carrying the section list, and the
// reading column. The rail is an IDE's file tree — you're reading a model's source
// files in order, and the current one should stay visible while you scroll.

export default function Learn() {
  const { modelId, slug } = useParams()
  const content = getModelContent(modelId)

  // No authored content — e.g. someone typed a learn URL for a model that has none.
  // Fall through to the training page, matching what the menu links such a model to.
  if (!modelId || !content) return <Navigate to={`/training/${modelId ?? ''}`} replace />

  // The epilogue is checked BEFORE the shape branch, because it hangs off the base
  // type: a paged model and a walkthrough model can both have one, and the page it
  // renders is the same either way.
  if (content.epilogue && slug === content.epilogue.slug) {
    return (
      <AbstractionPage
        modelId={modelId}
        content={content as typeof content & { epilogue: NonNullable<typeof content.epilogue> }}
      />
    )
  }

  // A walkthrough model is one continuous timeline rather than a sequence of pages,
  // and its rail seeks instead of navigating, so it owns its own layout. Everything
  // below this line is the paged flow, unchanged, and TypeScript narrows `content`
  // to PagedContent for it.
  if (content.kind === 'walkthrough') {
    return <Walkthrough modelId={modelId} content={content} chapterSlug={slug} />
  }

  const { sections } = content
  const index = slug ? sections.findIndex((s) => s.slug === slug) : 0
  // Unknown slug: bounce to the first section rather than render nothing.
  if (index === -1) return <Navigate to={`/training/${modelId}/learn`} replace />

  const section = sections[index]
  const Body = section.Body
  const prev = index > 0 ? sections[index - 1] : null
  const next = index < sections.length - 1 ? sections[index + 1] : null
  const learn = (s: string) => `/training/${modelId}/learn/${s}`

  return (
    <div className="learn-grid">
      <nav className="learn-rail" aria-label="Sections">
        <Link to="/training" className="learn-rail__back">
          &larr; All models
        </Link>
        <div className="learn-rail__model">{content.name}</div>
        <div className="learn-rail__count">
          {index + 1} of {sections.length}
        </div>

        {/* Table of contents: jump directly to any section. The current one is
            plain text rather than a link to itself, and carries the left rule. */}
        <div className="learn-rail__list">
          {sections.map((s, i) =>
            i === index ? (
              <span
                key={s.slug}
                className="learn-rail__item learn-rail__item--current"
                aria-current="page"
              >
                {s.title}
              </span>
            ) : (
              <Link key={s.slug} to={learn(s.slug)} className="learn-rail__item">
                {s.title}
              </Link>
            ),
          )}
        </div>

        {/* Two ways forward from the reading. Finding a dataset comes first
            because it is the one that decides what you build; training on the
            bundled datasets is always available underneath it. */}
        <div className="learn-rail__foot">
          <Link to={`/training/${modelId}/bridge`}>Find a dataset &rarr;</Link>
          <Link to={`/training/${modelId}`}>Start training &rarr;</Link>
        </div>
      </nav>

      <div className="learn-body">
        {/* .prose is the only hook the MDX output gets: the compiled pages are
            plain HTML with no wrapper of their own, so every heading, paragraph
            and code block is styled through descendant selectors from here. */}
        <div className="prose">
          <Body />
        </div>

        {/* On the last section, "Next" becomes the call to actually train. */}
        <nav className="learn-nav" aria-label="Section pagination">
          <span>
            {prev && <Link to={learn(prev.slug)}>&larr; {prev.title}</Link>}
          </span>
          <span>
            {next ? (
              <Link to={learn(next.slug)}>{next.title} &rarr;</Link>
            ) : (
              <Link to={`/training/${modelId}`}>Start training &rarr;</Link>
            )}
          </span>
        </nav>
      </div>
    </div>
  )
}
