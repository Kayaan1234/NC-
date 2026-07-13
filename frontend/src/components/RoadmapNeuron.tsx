import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { RungProgress } from '../api/types'

/**
 * The roadmap rendered as a single neuron, left → right in the direction of a
 * forward pass. Rung 0 ("the single neuron") is the soma; 0→1→2→3 is the axon
 * hillock/trunk; at rung 3 the axon forks into a short collateral to rung 4
 * (CNN, a side branch) and the long axon 5→6→7→8→9 that terminates at the
 * transformer. Topology is taken from the roadmap's prose dependency line and is
 * intentionally frontend-static — the backend has no prerequisites field.
 *
 * State encoding reuses the theme's signal language:
 *   completed → amber (the backward pass has run: mastered)
 *   unlocked  → cyan  (activations flowing: available now)
 *   locked    → dim periwinkle (a "COMING SOON" cell, not yet firing)
 * An edge lights only when BOTH endpoints are non-locked; a signal particle then
 * travels it. So as rungs unlock, the neuron lights up along its axon.
 */

interface Pos {
  x: number
  y: number
  r: number
}

// viewBox is 0 0 1000 470. Positions are hand-tuned for a neuron silhouette.
const LAYOUT: Record<number, Pos> = {
  0: { x: 94, y: 250, r: 30 }, // soma
  1: { x: 228, y: 222, r: 19 },
  2: { x: 352, y: 250, r: 19 },
  3: { x: 472, y: 230, r: 22 }, // axon fork
  4: { x: 590, y: 96, r: 18 }, // CNN collateral (up)
  5: { x: 602, y: 320, r: 19 },
  6: { x: 702, y: 344, r: 19 },
  7: { x: 792, y: 320, r: 19 },
  8: { x: 876, y: 346, r: 19 },
  9: { x: 958, y: 320, r: 25 }, // transformer terminal
}

const EDGES: Array<[number, number]> = [
  [0, 1], [1, 2], [2, 3], [3, 4], [3, 5], [5, 6], [6, 7], [7, 8], [8, 9],
]

/** Smooth cubic with horizontal tangents, so edges read as flowing axon rather
 *  than a straight wire graph. */
function edgePath(a: Pos, b: Pos): string {
  const dx = (b.x - a.x) * 0.42
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`
}

const STATUS_LABEL: Record<RungProgress['status'], string> = {
  completed: 'completed',
  unlocked: 'available',
  locked: 'coming soon',
}

interface Props {
  rungs: RungProgress[]
  currentRungNumber: number | null
}

export default function RoadmapNeuron({ rungs, currentRungNumber }: Props) {
  const reduced = useMemo(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  )

  const byNumber = useMemo(() => {
    const m = new Map<number, RungProgress>()
    for (const r of rungs) m.set(r.number, r)
    return m
  }, [rungs])

  // Default selection: the current rung, else the first available, else rung 0.
  const initialSelected = useMemo(() => {
    if (currentRungNumber != null && byNumber.has(currentRungNumber)) return currentRungNumber
    const firstOpen = rungs.find((r) => r.status !== 'locked')
    return firstOpen?.number ?? rungs[0]?.number ?? 0
  }, [currentRungNumber, byNumber, rungs])

  const [selected, setSelected] = useState<number>(initialSelected)
  const selectedRung = byNumber.get(selected) ?? null

  const nodeNumbers = rungs
    .map((r) => r.number)
    .filter((n) => n in LAYOUT)
    .sort((a, b) => a - b)

  const edges = EDGES.filter(([a, b]) => byNumber.has(a) && byNumber.has(b))

  const unlockedCount = rungs.filter((r) => r.status !== 'locked').length

  return (
    <div className="rn">
      <div className="rn-stage card">
        <ul className="rn-legend mono" aria-hidden="true">
          <li data-tone="fwd">available</li>
          <li data-tone="bwd">completed</li>
          <li data-tone="idle">coming soon</li>
        </ul>

        <svg
          className="rn-svg"
          viewBox="-8 44 1024 372"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={`Roadmap: ${unlockedCount} of ${rungs.length} rungs unlocked.`}
        >
          <defs>
            <radialGradient id="rn-halo-fwd">
              <stop offset="0%" stopColor="rgba(45,226,230,0.55)" />
              <stop offset="100%" stopColor="rgba(45,226,230,0)" />
            </radialGradient>
            <radialGradient id="rn-halo-bwd">
              <stop offset="0%" stopColor="rgba(255,159,69,0.5)" />
              <stop offset="100%" stopColor="rgba(255,159,69,0)" />
            </radialGradient>
          </defs>

          {/* dendrites feeding the soma — decorative "inputs" */}
          <g className="rn-arbor" aria-hidden="true">
            {[-46, -20, 6, 30].map((dy, i) => (
              <path
                key={i}
                className="rn-arbor-branch"
                d={`M ${LAYOUT[0].x - LAYOUT[0].r} ${LAYOUT[0].y} C ${LAYOUT[0].x - 44} ${
                  LAYOUT[0].y + dy * 0.5
                }, ${LAYOUT[0].x - 62} ${LAYOUT[0].y + dy}, ${LAYOUT[0].x - 84} ${LAYOUT[0].y + dy}`}
              />
            ))}
            {/* axon terminal arbor at the transformer */}
            {[-30, -8, 14, 34].map((dy, i) => (
              <path
                key={`t${i}`}
                className="rn-arbor-branch"
                d={`M ${LAYOUT[9].x + LAYOUT[9].r} ${LAYOUT[9].y} C ${LAYOUT[9].x + 26} ${
                  LAYOUT[9].y + dy * 0.5
                }, ${LAYOUT[9].x + 34} ${LAYOUT[9].y + dy}, ${LAYOUT[9].x + 44} ${LAYOUT[9].y + dy}`}
              />
            ))}
          </g>

          {/* edges */}
          <g className="rn-edges">
            {edges.map(([a, b]) => {
              const ra = byNumber.get(a)!
              const rb = byNumber.get(b)!
              const lit = ra.status !== 'locked' && rb.status !== 'locked'
              const tone = ra.status === 'completed' && rb.status === 'completed' ? 'bwd' : 'fwd'
              return (
                <path
                  key={`${a}-${b}`}
                  id={`rn-edge-${a}-${b}`}
                  className="rn-edge"
                  data-lit={lit}
                  data-tone={tone}
                  d={edgePath(LAYOUT[a], LAYOUT[b])}
                />
              )
            })}
          </g>

          {/* travelling signals on lit edges */}
          {!reduced &&
            edges.map(([a, b], i) => {
              const ra = byNumber.get(a)!
              const rb = byNumber.get(b)!
              if (ra.status === 'locked' || rb.status === 'locked') return null
              const tone = ra.status === 'completed' && rb.status === 'completed' ? 'bwd' : 'fwd'
              return (
                <circle key={`sig-${a}-${b}`} className="rn-signal" data-tone={tone} r={3}>
                  <animateMotion dur={`${2.1 + (i % 3) * 0.45}s`} repeatCount="indefinite" rotate="auto">
                    <mpath href={`#rn-edge-${a}-${b}`} />
                  </animateMotion>
                </circle>
              )
            })}

          {/* nodes */}
          <g className="rn-nodes">
            {nodeNumbers.map((n) => {
              const r = byNumber.get(n)!
              const pos = LAYOUT[n]
              const isCurrent = currentRungNumber === n
              const isSelected = selected === n
              const lit = r.status !== 'locked'
              const label = `Rung ${n}: ${r.title} — ${STATUS_LABEL[r.status]}${
                r.exercises_total > 0 ? `, ${r.exercises_completed} of ${r.exercises_total} done` : ''
              }`
              return (
                <g
                  key={n}
                  className="rn-node"
                  data-status={r.status}
                  data-current={isCurrent || undefined}
                  data-selected={isSelected || undefined}
                  transform={`translate(${pos.x} ${pos.y})`}
                  role="button"
                  tabIndex={0}
                  aria-label={label}
                  aria-pressed={isSelected}
                  onClick={() => setSelected(n)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setSelected(n)
                    }
                  }}
                >
                  <title>{label}</title>
                  {isCurrent && <circle className="rn-pulse" r={pos.r + 7} />}
                  {lit && <circle className="rn-halo" r={pos.r * 2.5} fill={`url(#rn-halo-${r.status === 'completed' ? 'bwd' : 'fwd'})`} />}
                  {/* invisible larger hit area for easy clicking/tapping */}
                  <circle className="rn-hit" r={pos.r + 12} />
                  <circle className="rn-core" r={pos.r} />
                  <text className="rn-num mono" dy="0.34em">
                    {String(n).padStart(2, '0')}
                  </text>
                </g>
              )
            })}
          </g>
        </svg>
      </div>

      {selectedRung && (
        <aside className="rn-detail card" data-status={selectedRung.status} aria-live="polite">
          <div className="rn-detail-head">
            <span className="rn-detail-kicker mono">
              rung {String(selectedRung.number).padStart(2, '0')} · {STATUS_LABEL[selectedRung.status]}
            </span>
            <h3>{selectedRung.title}</h3>
          </div>

          <div className="rn-detail-body">
            {selectedRung.exercises_total > 0 ? (
              <>
                <div className="rn-progress" aria-hidden="true">
                  <span
                    className="rn-progress-fill"
                    style={{
                      width: `${(selectedRung.exercises_completed / selectedRung.exercises_total) * 100}%`,
                    }}
                  />
                </div>
                <p className="rn-detail-meta mono">
                  {selectedRung.exercises_completed} / {selectedRung.exercises_total} exercises
                </p>
              </>
            ) : (
              <p className="rn-detail-meta mono">not published yet</p>
            )}

            <RungAction rung={selectedRung} isCurrent={currentRungNumber === selectedRung.number} />
          </div>
        </aside>
      )}
    </div>
  )
}

function RungAction({ rung, isCurrent }: { rung: RungProgress; isCurrent: boolean }) {
  // A locked or not-yet-authored rung has no landing page to open.
  if (rung.status === 'locked' || rung.exercises_total === 0) {
    return (
      <button className="btn btn-ghost btn-sm" disabled>
        {rung.exercises_total === 0 ? 'Coming soon' : 'Locked'}
      </button>
    )
  }
  // Available/completed authored rungs open their title page (the suite entry).
  const label = rung.status === 'completed' ? 'Review rung' : isCurrent ? 'Begin here' : 'Open rung'
  return (
    <Link className="btn btn-primary btn-sm" to={`/rung/${rung.number}`}>
      {label}
    </Link>
  )
}
