import { useState } from 'react'

/**
 * The exercise-suite navigation. It lives ONLY inside the suite (rendered by the
 * rung pages), so it appears when you enter a rung and is gone the moment you
 * leave. At rest it collapses to a slim rail pinned to the left edge — a chevron,
 * a vertical "EXERCISES" label, and one dot per exercise — so it's clearly
 * discoverable without taking space. Hovering, focusing, or tapping the handle
 * expands it into the drawer of quick-jump links.
 *
 * The links are intentionally inert placeholders: the backend exposes no
 * per-exercise data or routes yet (only rung-level progress counts), so there's
 * nothing truthful to link to. When those land, drop the `disabled` and point
 * each button at its exercise route.
 */

/** Per-exercise state, merged from the backend feed onto the authored
 *  curriculum: 'coming_soon' = not authored/seeded yet; the rest reflect the
 *  user's real progress ('next' is the resume point). */
export type SuiteExerciseState =
  | 'completed'
  | 'in_progress'
  | 'next'
  | 'locked'
  | 'coming_soon'

export interface SuiteExercise {
  slug: string
  name: string
  readOnly: boolean
  state: SuiteExerciseState
}

interface Props {
  rungNumber: number
  rungTitle: string
  exercises: SuiteExercise[]
}

export default function ExerciseRail({ rungNumber, rungTitle, exercises }: Props) {
  const [open, setOpen] = useState(false)
  const pad = (n: number) => String(n).padStart(2, '0')
  const currentIndex = exercises.findIndex((e) => e.state === 'next')

  return (
    <aside
      className="ex-rail"
      data-open={open || undefined}
      aria-label={`Rung ${pad(rungNumber)} exercises`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      // Keep it open while any child has focus (keyboard nav); close when focus
      // leaves the rail entirely.
      onFocus={() => setOpen(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false)
      }}
    >
      {/* Slim rail — the always-visible signpost. */}
      <div className="ex-rail-strip" aria-hidden={open || undefined}>
        <button
          type="button"
          className="ex-rail-handle"
          aria-expanded={open}
          aria-controls="ex-rail-drawer"
          aria-label={open ? 'Collapse exercises' : 'Expand exercises'}
          onClick={() => setOpen((o) => !o)}
        >
          <span className="ex-rail-chevron" aria-hidden="true">
            ›
          </span>
        </button>
        <span className="ex-rail-label mono">EXERCISES</span>
        <ul className="ex-rail-dots" aria-hidden="true">
          {exercises.map((ex, i) => (
            <li
              key={i}
              className="ex-rail-dot"
              data-state={ex.state}
              data-current={i === currentIndex || undefined}
            />
          ))}
        </ul>
      </div>

      {/* Drawer — revealed on hover / focus / tap. */}
      <nav id="ex-rail-drawer" className="ex-rail-drawer" aria-label="Jump to an exercise">
        <p className="ex-rail-kicker mono">
          rung {pad(rungNumber)} · {rungTitle.toLowerCase()}
        </p>
        <ul className="ex-rail-list">
          {exercises.map((ex, i) => (
            <li key={i}>
              <button
                type="button"
                className="ex-link"
                data-state={ex.state}
                data-current={i === currentIndex || undefined}
                disabled
                title={ex.state === 'coming_soon' ? 'Not published yet' : 'Exercise view is coming soon'}
              >
                <span className="ex-link-idx mono">{pad(i + 1)}</span>
                <span className="ex-link-name">{ex.name}</span>
                {ex.readOnly && <span className="ex-link-tag mono">read</span>}
              </button>
            </li>
          ))}
        </ul>
        <p className="ex-rail-foot mono">unlocked as you complete each step</p>
      </nav>
    </aside>
  )
}
