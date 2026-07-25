import { Link, Navigate, useParams } from 'react-router-dom'
import { getModelContent } from '../content'

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

export default function Learn() {
  const { modelId, slug } = useParams()
  const content = getModelContent(modelId)

  // No authored content — e.g. someone typed a learn URL for a model that has none.
  // Fall through to the training page, matching what the menu links such a model to.
  if (!modelId || !content) return <Navigate to={`/training/${modelId ?? ''}`} replace />

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
    <div>
      <p>
        <Link to="/training">← All models</Link>
      </p>
      <p>
        {content.name} — {section.title} ({index + 1} of {sections.length})
      </p>

      {/* Table of contents: jump directly to any section. */}
      <ul>
        {sections.map((s, i) => (
          <li key={s.slug}>
            {i === index ? s.title : <Link to={learn(s.slug)}>{s.title}</Link>}
          </li>
        ))}
      </ul>

      {/* The authored page: prose + fenced code, rendered as plain HTML by MDX. */}
      <Body />

      {/* On the last section, "Next" becomes the call to actually train. */}
      <p>
        {prev && (
          <>
            <Link to={learn(prev.slug)}>← Previous</Link>{' '}
          </>
        )}
        {next ? (
          <Link to={learn(next.slug)}>Next →</Link>
        ) : (
          <Link to={`/training/${modelId}`}>Start training →</Link>
        )}
      </p>
      <p>
        <Link to={`/training/${modelId}/learn`}>Return to beginning</Link>
      </p>
      <p>
        <Link to={`/training/${modelId}`}>Skip to training</Link>
      </p>
    </div>
  )
}
