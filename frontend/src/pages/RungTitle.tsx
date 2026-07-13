import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { RungExercises } from '../api/types'
import ExerciseRail, { type SuiteExercise } from '../components/ExerciseRail'
import SingleNeuronDiagram from '../components/SingleNeuronDiagram'

/**
 * The Rung 0 title page — the entry to the exercise suite. Rather than dropping
 * the learner straight into "essential maths", this landing frames the whole
 * rung and cross-links its exercises, which matter because the rung's parts are
 * heavily interdependent and backreferenced.
 *
 * The six-item breakdown is the *authored curriculum* (what Rung 0 will contain);
 * GET /rungs/0/exercises overlays the *live* per-user state onto it — completed /
 * in-progress / next (the resume point) / locked for exercises that exist, and
 * "coming soon" for ones not yet seeded. So the page keeps its designed shape and
 * lights up as content is authored and the learner progresses.
 *
 * Only Rung 0 is authored; other numbers render a "not yet" state. The action
 * buttons stay disabled: there's no exercise-workspace route to open yet.
 */

// The authored curriculum. `slug` must match the seed slug so the backend feed
// can be merged in by slug; only `essential-maths` is seeded today.
const RUNG0_CURRICULUM: Array<{ slug: string; name: string; readOnly: boolean }> = [
  { slug: 'essential-maths', name: 'The essential maths', readOnly: false },
  { slug: 'forward-propagation', name: 'Forward propagation', readOnly: false },
  { slug: 'the-loss-function', name: 'The loss function', readOnly: false },
  { slug: 'learning', name: 'Learning', readOnly: false },
  { slug: 'putting-it-all-together', name: 'Putting it all together', readOnly: true },
  { slug: 'numerical-gradient-check', name: 'Numerical gradient check', readOnly: true },
]

const STATE_LABEL: Record<SuiteExercise['state'], string> = {
  completed: 'done',
  in_progress: 'in progress',
  next: 'next',
  locked: 'locked',
  coming_soon: 'coming soon',
}

/** Overlay the backend feed onto the authored curriculum. Before the fetch
 *  resolves (data === null) every item reads as "coming soon" — a neutral,
 *  non-blocking placeholder that fills in once progress loads. */
function mergeCurriculum(data: RungExercises | null): SuiteExercise[] {
  const bySlug = new Map((data?.exercises ?? []).map((e) => [e.slug, e]))
  const next = data?.next_incomplete_slug ?? null
  return RUNG0_CURRICULUM.map((c) => {
    const be = bySlug.get(c.slug)
    if (!be) return { slug: c.slug, name: c.name, readOnly: c.readOnly, state: 'coming_soon' }
    let state: SuiteExercise['state']
    if (be.status === 'completed') state = 'completed'
    else if (be.status === 'in_progress') state = 'in_progress'
    else state = be.slug === next ? 'next' : 'locked'
    return { slug: c.slug, name: c.name, readOnly: be.read_only, state }
  })
}

export default function RungTitle() {
  const { number } = useParams()
  const n = Number(number)

  // React Router's <Routes> doesn't reset scroll on navigation, and "Begin here"
  // sits below the fold on the dashboard — without this the title page would open
  // scrolled into the middle of the neuron, hiding the title it exists to show.
  // Scoped here (not the shared Layout) so other routes keep their scroll.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [number])

  const [data, setData] = useState<RungExercises | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isRung0 = n === 0
  useEffect(() => {
    if (!isRung0) return
    let alive = true
    api
      .rungExercises(0)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e instanceof ApiError ? e.message : 'Could not load your progress.'))
    return () => {
      alive = false
    }
  }, [isRung0])

  const exercises = useMemo(() => mergeCurriculum(data), [data])
  const nextName = useMemo(() => {
    const slug = data?.next_incomplete_slug
    return slug ? (RUNG0_CURRICULUM.find((c) => c.slug === slug)?.name ?? null) : null
  }, [data])

  if (!isRung0) return <NotAuthoredYet />

  return (
    <div className="suite">
      <ExerciseRail rungNumber={0} rungTitle="The single neuron" exercises={exercises} />

      <article className="rung-title">
        <header className="rung-title-head">
          <p className="eyebrow mono">
            <Link to="/dashboard" className="rung-back">
              ← roadmap
            </Link>
            <span className="rung-eyebrow-num">rung 00</span>
          </p>
          <h1>
            The <span className="grad-fwd">single neuron</span>.
          </h1>
        </header>

        <SingleNeuronDiagram />

        <p className="lede">
          This is the foundation of neural computing — the concepts you build here carry forward
          into every later rung of the roadmap. You&rsquo;ll implement the essentials by hand:
          activation functions, loss functions, and how a model actually learns, using basic linear
          algebra and calculus.
        </p>

        <section className="rung-breakdown" aria-labelledby="breakdown-h">
          <h2 id="breakdown-h" className="section-kicker mono">
            the breakdown of this rung
          </h2>
          {error && (
            <p className="rung-sync-error mono" role="alert">
              {error} — showing the curriculum without your progress.
            </p>
          )}
          <ol className="rung-steps">
            {exercises.map((ex, i) => (
              <li key={ex.slug} className="rung-step" data-state={ex.state} data-readonly={ex.readOnly || undefined}>
                <span className="rung-step-idx mono">{String(i + 1).padStart(2, '0')}</span>
                <span className="rung-step-name">{ex.name}</span>
                {ex.readOnly && <span className="rung-step-tag mono">read only</span>}
                <span className="rung-step-lock mono" aria-hidden="true">
                  {STATE_LABEL[ex.state]}
                </span>
              </li>
            ))}
          </ol>
          <p className="rung-gate mono">each step unlocks the moment you finish the one before it</p>
        </section>

        <div className="rung-cta">
          <button
            type="button"
            className="btn btn-primary"
            disabled
            title="Exercise workspace is coming soon"
          >
            {nextName ? `Start: ${nextName} →` : 'Continue this rung →'}
          </button>
          <span className="rung-cta-note mono">exercise workspace coming soon</span>
        </div>
      </article>
    </div>
  )
}

function NotAuthoredYet() {
  return (
    <div className="suite">
      <article className="rung-title rung-title-empty">
        <p className="eyebrow mono">
          <Link to="/dashboard" className="rung-back">
            ← roadmap
          </Link>
        </p>
        <h1>Coming soon.</h1>
        <p className="lede">
          This rung isn&rsquo;t published yet. Rung 00 — the single neuron — is where the roadmap
          begins.
        </p>
        <Link to="/rung/0" className="btn btn-primary">
          Go to rung 00
        </Link>
      </article>
    </div>
  )
}
